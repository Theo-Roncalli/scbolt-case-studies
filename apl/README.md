# APL case study

Reproduction of the PLZF-RARα acute promyelocytic leukemia (APL) analyses presented in the scBOLT manuscript, based on the dataset from [Poplineau et al. (2022)](https://ashpublications.org/blood/article/140/22/2358/486349/Noncanonical-EZH2-drives-retinoic-acid-resistance).

## Entry points

| Parameter file  | Input source       | Output directory |
| --------------- | ------------------ | ---------------- |
| `params-gsm.mk` | GEO count matrices | `project_gsm/`   |
| `params-sra.mk` | SRA raw reads      | `project_sra/`   |

`params-gsm.mk` is the recommended entry point for reproducing the manuscript results.

`params-sra.mk` demonstrates the use of the full scBOLT framework starting from raw sequencing reads.

> **Note (SRA entry point only)**
> Unlike the GSM-based reproduction path, this entry point depends on genome annotations and RepeatMasker tracks retrieved from upstream providers. As these resources are not distributed through archived releases, some intermediate results may vary over time.

## Reproducing the analyses

### From GEO matrices

Initialize the project:

```bash
scbolt init params-gsm.mk
```

Before running the inference, you may inspect the project configuration and dependencies with:

```bash
scbolt check bn-submin
```

Run the inference:

```bash
scbolt bn-submin
```

### From SRA reads

Run the project:

```bash
scbolt init params-sra.mk
scbolt bn-submin
```

### Additional analyses

Potency scores reported in the manuscript can be reproduced from the GSM-based reproduction path with:

```bash
scbolt init params-gsm.mk
scbolt potency
```

GO enrichment tables can also be regenerated directly from the processed APL AnnData object with:

```bash
conda activate scbolt-cs
python scripts/goea.py data/omics/integrated.h5ad
```

The output workbook is written to `results/goea/basic.xlsx`. The DEA table used
for enrichment is kept in `results/goea/markers.csv`.

## Notebooks

The `notebooks/` directory contains the readable figure-generation notebooks used during the preparation of the manuscript:

- `notebooks/omics.ipynb`: transcriptomic integration, potency analysis, macrostate characterisation, and binarisation diagnostics.
- `notebooks/bn.ipynb`: Boolean-network specification, inference, and downstream analyses.

`omics.ipynb` assumes that the case-study data have been generated or copied into `apl/data/`. Figures are exported to `apl/figures/`.

### Running `omics.ipynb`

From `apl/`, create and activate the notebook environment:

```bash
conda env create -f ../envs/scbolt-cs.yml
conda activate scbolt-cs
```

Launch one of the notebooks:

```bash
jupyter lab notebooks/omics.ipynb
jupyter lab notebooks/bn.ipynb
```

If Jupyter does not list the environment as a kernel, register it once:

```bash
python -m ipykernel install --user --name scbolt-cs --display-name "Python (scbolt-cs)"
```

## Repository structure

```text
apl/
├── params-gsm.mk      # parameters for the GEO-based entry point
├── params-sra.mk      # parameters for the SRA-based entry point
├── spec.yml           # BoNesis specification
├── notebooks/         # exploratory analyses
└── figures/           # manuscript figure generation
```
