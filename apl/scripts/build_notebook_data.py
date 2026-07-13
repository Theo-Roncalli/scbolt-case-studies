#!/usr/bin/env python3
"""Export the scBOLT results required by the APL notebooks."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import anndata as ad
import bonesistools as bt
import pandas as pd


APL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_DIR = APL_DIR / "project_gsm"
DEFAULT_OUTPUT_DIR = APL_DIR / "data"
LEGACY_OUTPUTS = ("potency", "mstates_bin.csv", "hvgs.txt")
DEFAULT_BIN_METHOD = "consensus"
EXPECTED_HVG_COUNT = 3228
MARKER_GENES = ["S100a8", "S100a9", "Ly6g", "Ngp"]
INTEGRATED_H5AD = Path("omics/integrated.h5ad")
CONDITION_H5ADS = {
    Path("omics/ctrl.h5ad"),
    Path("omics/treated.h5ad"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the minimal scBOLT results used by the APL notebooks."
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=DEFAULT_PROJECT_DIR,
        help=f"scBOLT project directory (default: {DEFAULT_PROJECT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"notebook data directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace existing bn/ and omics/ output directories",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and display the export without copying files",
    )
    return parser.parse_args()


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"required result not found: {path}")
    return path


def discover_macrostate_method(project_dir: Path) -> tuple[str, Path, Path]:
    root = project_dir / "omics" / "mstates"
    candidates = []

    if root.is_dir():
        for method_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            ctrl = method_dir / "ctrl" / "mstates.h5ad"
            treated = method_dir / "treated" / "mstates.h5ad"
            if ctrl.is_file() and treated.is_file():
                candidates.append((method_dir.name, ctrl, treated))

    if not candidates:
        raise FileNotFoundError(f"no complete macrostate result found under {root}")
    if len(candidates) > 1:
        methods = ", ".join(method for method, _, _ in candidates)
        raise RuntimeError(f"multiple macrostate methods found under {root}: {methods}")

    return candidates[0]


def discover_binarisation_method(project_dir: Path) -> str:
    metadata_file = project_dir / "infer" / "spec" / "mstates.scbolt.json"
    if not metadata_file.is_file():
        return DEFAULT_BIN_METHOD

    metadata = json.loads(metadata_file.read_text())
    params_file = Path(metadata["params_file"])
    if not params_file.is_file():
        params_file = APL_DIR / params_file.name
    if not params_file.is_file():
        return DEFAULT_BIN_METHOD

    pattern = re.compile(r"^\s*BIN_METHOD\s*(?:\?|:)?=\s*([^\s#]+)")
    for line in params_file.read_text().splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1)
    return DEFAULT_BIN_METHOD


def discover_bn_files(project_dir: Path) -> dict[Path, Path]:
    source_dir = project_dir / "infer" / "bn" / "submin"
    solution_dirs = sorted(
        (
            path
            for path in source_dir.iterdir()
            if path.is_dir() and path.name.isdigit()
        ),
        key=lambda path: int(path.name),
    ) if source_dir.is_dir() else []

    if not solution_dirs:
        raise FileNotFoundError(f"no numerical BN solution found under {source_dir}")

    files = {}
    for solution_dir in solution_dirs:
        for filename in ("model.bnet", "configs.csv"):
            source = require_file(solution_dir / filename)
            files[Path("bn") / solution_dir.name / filename] = source

    return files


def build_export_plan(project_dir: Path) -> tuple[str, str, dict[Path, Path]]:
    project_dir = project_dir.resolve()
    method, ctrl, treated = discover_macrostate_method(project_dir)
    bin_method = discover_binarisation_method(project_dir)

    files = discover_bn_files(project_dir)
    files.update(
        {
            Path("omics/ctrl.h5ad"): ctrl,
            Path("omics/treated.h5ad"): treated,
            Path("omics/integrated.h5ad"): require_file(
                project_dir / "omics" / "annot" / "integrated" / "annot.h5ad"
            ),
            Path("omics/mstates_bin.csv"): require_file(
                project_dir
                / "bin"
                / bin_method
                / method
                / "mstates_bin.csv"
            ),
            Path("omics/potency_ctrl.csv"): require_file(
                project_dir
                / "omics"
                / "trajectories"
                / "potency"
                / "ctrl"
                / "potency.csv"
            ),
            Path("omics/potency_treated.csv"): require_file(
                project_dir
                / "omics"
                / "trajectories"
                / "potency"
                / "treated"
                / "potency.csv"
            ),
        }
    )
    return method, bin_method, files


def path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def export_integrated_h5ad(source: Path, destination: Path) -> None:
    adata = ad.read_h5ad(source, backed="r")
    try:
        marker_expression = adata[:, MARKER_GENES].to_memory().layers["log-norm"]
        exported = ad.AnnData(
            obs=adata.obs.loc[:, ["condition", "label"]].copy(),
            var=pd.DataFrame(index=MARKER_GENES),
            obsm={"X_umap": adata.obsm["X_umap"].copy()},
            layers={"log-norm": marker_expression},
        )
    finally:
        adata.file.close()

    exported.write_h5ad(destination, compression="gzip")


def export_condition_h5ad(source: Path, destination: Path) -> None:
    adata = ad.read_h5ad(source, backed="r")
    try:
        exported = ad.AnnData(
            obs=adata.obs.loc[:, ["macrostate"]].copy(),
            obsm={"X_umap": adata.obsm["X_umap"].copy()},
        )
    finally:
        adata.file.close()

    exported.write_h5ad(destination, compression="gzip")


def estimated_export_size(files: dict[Path, Path]) -> int:
    copied_size = sum(
        source.stat().st_size
        for relative_path, source in files.items()
        if relative_path not in CONDITION_H5ADS | {INTEGRATED_H5AD}
    )
    return copied_size + 100 * 1024**2


def restrict_binarisation_to_hvgs(integrated_file: Path, output_dir: Path) -> None:
    binarisation_file = output_dir / "omics" / "mstates_bin.csv"

    adata = ad.read_h5ad(integrated_file)
    hvgs = (
        bt.omics.pp.hvg(
            adata,
            expression="log-norm",
            method="binning",
            n_bins=20,
            n_features=None,
            batch_key="condition",
            batch_selection="rank",
            inplace=False,
        )
        .query("selected")
        .index.tolist()
    )
    if len(hvgs) != EXPECTED_HVG_COUNT:
        raise RuntimeError(
            f"expected {EXPECTED_HVG_COUNT} HVGs but selected {len(hvgs)}"
        )

    binarisation = pd.read_csv(binarisation_file, index_col=0)
    missing = sorted(set(hvgs) - set(binarisation.columns))
    if missing:
        raise RuntimeError(
            f"{len(missing)} HVGs are absent from {binarisation_file}: "
            + ", ".join(missing[:5])
        )

    binarisation.loc[:, hvgs].to_csv(binarisation_file)


def export(files: dict[Path, Path], output_dir: Path, force: bool) -> None:
    output_dir = output_dir.resolve()
    managed_dirs = [output_dir / "bn", output_dir / "omics"]
    legacy_outputs = [output_dir / path for path in LEGACY_OUTPUTS]
    existing = [path for path in (*managed_dirs, *legacy_outputs) if path.exists()]

    if existing and not force:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"output already exists: {names}; use --force to replace it")

    required_size = estimated_export_size(files)
    reclaimable_size = sum(path_size(path) for path in existing)
    output_dir.mkdir(parents=True, exist_ok=True)
    available_size = shutil.disk_usage(output_dir).free + reclaimable_size

    if required_size > available_size:
        raise OSError(
            "insufficient disk space: "
            f"need {format_size(required_size)}, "
            f"have {format_size(available_size)} after replacing existing outputs"
        )

    for path in existing:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    for relative_path, source in files.items():
        destination = output_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if relative_path == INTEGRATED_H5AD:
            export_integrated_h5ad(source, destination)
        elif relative_path in CONDITION_H5ADS:
            export_condition_h5ad(source, destination)
        else:
            shutil.copy2(source, destination)

    restrict_binarisation_to_hvgs(files[INTEGRATED_H5AD], output_dir)


def main() -> None:
    args = parse_args()
    try:
        method, bin_method, files = build_export_plan(args.project_dir)
        bn_count = sum(path.name == "model.bnet" for path in files)
        total_size = estimated_export_size(files)

        print(f"project: {args.project_dir.resolve()}")
        print(f"output: {args.output_dir.resolve()}")
        print(f"macrostate method: {method}")
        print(f"binarization method: {bin_method}")
        print(f"HVGs: automatic cutoff (expected: {EXPECTED_HVG_COUNT})")
        print(f"Boolean networks: {bn_count}")
        print(f"files: {len(files)}")
        print(f"estimated size (upper bound): {format_size(total_size)}")

        if args.dry_run:
            print("dry run: no files copied")
            return

        export(files, args.output_dir, force=args.force)
    except (OSError, RuntimeError) as error:
        message = f"error: {error}"
        if "potency" in str(error):
            message += "\nrun `scbolt potency` before exporting notebook data"
        raise SystemExit(message) from None

    print("export complete")


if __name__ == "__main__":
    main()
