#!/usr/bin/env python

from __future__ import annotations

import gzip
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import anndata as ad
import bonesistools as bt
import pandas as pd
from goatools.anno.genetogo_reader import Gene2GoReader
from goatools.goea.go_enrichment_ns import GOEnrichmentStudyNS
from goatools.obo_parser import GODag


APL_DIR = Path(__file__).resolve().parents[1]
GO_DIR = APL_DIR / "resources" / "go"
RESULTS_DIR = APL_DIR / "results" / "goea"

GROUPBY = "label"
EXPRESSION = "log-norm"
ORGANISM = "mouse"
GENEINFO_VERSION = "bundled"
GENE_TYPE = "name"
ANNOTATION_TYPE = "gene_id"

DEA_METHOD = "wilcoxon"
DEA_ALPHA = 0.05
DEA_LOGFC = 0.25
DEA_CORRECTION = "benjamini-hochberg"

GO_RESOURCES = {
    "basic": GO_DIR / "go_basic.obo",
}
GENE2GO = GO_DIR / "gene2go.gz"
GO_NAMESPACE_ORDER = {"BP": 0, "MF": 1, "CC": 2}


def log(message: str) -> None:
    print(f"[goea] {message}", flush=True)


def read_gene2go(path: Path):
    if path.suffix != ".gz":
        return Gene2GoReader(path, taxids=[10090]).get_ns2assc()

    with tempfile.TemporaryDirectory(prefix="apl-gene2go-") as tmpdir:
        gene2go_path = Path(tmpdir) / "gene2go"
        with gzip.open(path, "rb") as infile:
            with gene2go_path.open("wb") as outfile:
                shutil.copyfileobj(infile, outfile)
        return Gene2GoReader(gene2go_path, taxids=[10090]).get_ns2assc()


def read_go_definitions(path: Path) -> dict[str, str]:
    definitions = {}
    go_id = None
    definition = None

    with path.open() as reader:
        for line in reader:
            if re.search(r"^id: GO:[0-9]{7}", line):
                go_id = re.findall(r"GO:[0-9]{7}|$", line)[0]
            elif re.search(r'^def: ".+\."', line):
                definition = re.findall(r'^def: ".+\."|$', line)[0]
                definition = re.sub(r'^def: "', "", definition)
                definition = re.sub(r'"$', "", definition)
            elif line == "\n":
                if go_id and definition:
                    definitions[go_id] = definition
                go_id = None
                definition = None

    return definitions


def ordered_groups(adata: ad.AnnData, obs: str) -> list[str]:
    values = adata.obs[obs]
    if hasattr(values, "cat"):
        return [str(value) for value in values.cat.categories]
    return [str(value) for value in pd.unique(values.dropna())]


def save_dea_outputs(adata: ad.AnnData, outdir: Path) -> pd.DataFrame:
    outdir.mkdir(parents=True, exist_ok=True)
    markers_file = outdir / "markers.csv"

    log(
        "ranking genes "
        f"(groupby={GROUPBY}, expression={EXPRESSION}, method={DEA_METHOD})"
    )
    markers = bt.sct.tl.dea(
        adata,
        groupby=GROUPBY,
        method=DEA_METHOD,
        expression=EXPRESSION,
        is_log=True,
        correction=DEA_CORRECTION,
        alpha=DEA_ALPHA,
        filter_logfoldchanges=lambda values: values > DEA_LOGFC,
    )
    markers = markers.rename(columns={"feature": "gene"})
    markers = markers[
        ["group", "gene", "statistics", "pvals", "pvals_adj", "logfoldchanges"]
    ]
    markers["group"] = markers["group"].astype(str)
    markers = markers.sort_values(
        by=["group", "statistics"],
        ascending=[True, False],
        kind="mergesort",
    ).reset_index(drop=True)

    log(f"saving DEA table ({markers_file})")
    markers.to_csv(markers_file, index=False)

    return markers


def sheet_name(value: object) -> str:
    name = re.sub(r"[\[\]:*?/\\]", "_", str(value))
    return name[:31] or "sheet"


def to_gene_ids(genes: Iterable[str], genesyn) -> set[int]:
    converted = genesyn(
        set(genes),
        input_identifier_type=GENE_TYPE,
        output_identifier_type=ANNOTATION_TYPE,
    )
    gene_ids = set()
    for gene_id in converted:
        if isinstance(gene_id, str) and gene_id.isnumeric():
            gene_ids.add(int(gene_id))
    return gene_ids


def sort_goea_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    sort_columns = []
    ascending = []

    if "NS" in df.columns:
        df = df.assign(
            _namespace_order=df["NS"]
            .map(GO_NAMESPACE_ORDER)
            .fillna(len(GO_NAMESPACE_ORDER))
        )
        sort_columns.append("_namespace_order")
        ascending.append(True)

    if "p_fdr_bh" in df.columns:
        sort_columns.append("p_fdr_bh")
        ascending.append(True)

    if sort_columns:
        df = df.sort_values(sort_columns, ascending=ascending, kind="mergesort")

    return df.drop(columns="_namespace_order", errors="ignore")


def goea_dataframe(results, go_definitions: dict[str, str], genesyn) -> pd.DataFrame:
    df = pd.DataFrame([vars(result) for result in results])
    if df.empty:
        return df

    if "GO" in df:
        df["definition"] = df["GO"].map(go_definitions)
    if "study_items" in df:
        df["genes"] = df["study_items"].apply(
            lambda gene_ids: ", ".join(
                str(gene)
                for gene in genesyn(
                    [str(gene_id) for gene_id in gene_ids],
                    input_identifier_type="gene_id",
                    output_identifier_type="official_name",
                )
                if gene is not None
            )
        )

    preferred = [
        "GO",
        "NS",
        "name",
        "definition",
        "p_fdr_bh",
        "enrichment",
        "ratio_in_study",
        "ratio_in_pop",
        "study_count",
        "study_n",
        "pop_count",
        "pop_n",
        "study_items",
        "genes",
    ]
    columns = [column for column in preferred if column in df.columns]
    columns += [column for column in df.columns if column not in columns]
    return sort_goea_dataframe(df.loc[:, columns])


def run_goea(
    markers: pd.DataFrame,
    background: Iterable[str],
    adata: ad.AnnData,
    outdir: Path,
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    log("loading NCBI gene synonyms")
    genesyn = bt.dbs.ncbi.genesyn(
        organism=ORGANISM,
        version=GENEINFO_VERSION,
    )
    background_ids = to_gene_ids(background, genesyn)

    log(f"loading gene-to-GO associations ({GENE2GO})")
    associations = read_gene2go(GENE2GO)
    for namespace, gene_id2go in associations.items():
        log(f"{namespace}: {len(gene_id2go):,} annotated {ORGANISM} genes")

    study_genes = {
        group: to_gene_ids(markers.loc[markers["group"] == group, "gene"], genesyn)
        for group in ordered_groups(adata, GROUPBY)
    }

    for resource_name, go_file in GO_RESOURCES.items():
        outfile = outdir / f"{resource_name}.xlsx"
        log(f"loading gene ontology ({go_file})")
        go_dag = GODag(obo_file=go_file, prt=open(os.devnull, "w"))
        go_definitions = read_go_definitions(go_file)

        goea = GOEnrichmentStudyNS(
            pop=background_ids,
            ns2assoc=associations,
            godag=go_dag,
            propagate_counts=False,
            alpha=0.05,
            methods=["fdr_bh"],
            log=open(os.devnull, "w"),
        )

        log(f"running GOEA ({resource_name})")
        wrote_sheet = False
        with pd.ExcelWriter(outfile) as writer:
            for group, gene_ids in study_genes.items():
                results = goea.run_study(study_ids=gene_ids, log=open(os.devnull, "w"))
                significant = [result for result in results if result.p_fdr_bh < 0.05]
                log(f"{group}: {len(significant)} significant GO terms")
                if not significant:
                    continue

                goea_dataframe(significant, go_definitions, genesyn).to_excel(
                    writer,
                    sheet_name=sheet_name(group),
                    index=False,
                )
                wrote_sheet = True

            if not wrote_sheet:
                pd.DataFrame({"message": ["no significant GOEA result"]}).to_excel(
                    writer,
                    sheet_name="summary",
                    index=False,
                )

        log(f"saving GOEA workbook ({outfile})")


def main(h5ad_file: str) -> None:
    h5ad_path = Path(h5ad_file).resolve()
    if not h5ad_path.exists():
        raise FileNotFoundError(h5ad_path)

    for path in [GENE2GO, *GO_RESOURCES.values()]:
        if not path.exists():
            raise FileNotFoundError(path)

    log(f"loading AnnData ({h5ad_path})")
    adata = ad.read_h5ad(h5ad_path)
    if GROUPBY not in adata.obs:
        raise KeyError(f"{GROUPBY!r} not found in adata.obs")
    if EXPRESSION not in adata.layers:
        raise KeyError(f"{EXPRESSION!r} not found in adata.layers")

    markers = save_dea_outputs(adata, RESULTS_DIR)
    run_goea(markers, adata.var_names, adata, RESULTS_DIR)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: python {Path(__file__).name} <integrated.h5ad>")
    main(sys.argv[1])
