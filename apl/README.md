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

Optionally validate the project:

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

## Notebooks

The `notebooks/` directory contains exploratory analyses and figure-generation notebooks used during the preparation of the manuscript.

Create and activate the dedicated case-study environment:

```bash
conda env create -f ../envs/scbolt-case.yml
conda activate scbolt-cs
```

Launch JupyterLab with:

```bash
jupyter lab
```

## Repository structure

```text
apl/
├── params-gsm.mk      # GEO-based reproduction path
├── params-sra.mk      # SRA-based reproduction path
├── spec.yml           # BoNesis specification
├── notebooks/         # exploratory analyses
└── figures/           # manuscript figure generation
```
