# scBOLT Case Studies

This repository contains reproducible case studies accompanying the scBOLT manuscript.

Each case study provides:

* parameter files used in the manuscript;
* BoNesis specifications;
* notebooks used for exploratory analyses and figure generation;
* instructions for reproducing the reported results.

## Requirements

Install scBOLT from the main repository:

```bash
git clone https://github.com/bnediction/scbolt.git
cd scbolt
bash config.sh
```

See the main repository for installation details and documentation:

* https://github.com/bnediction/scbolt

Additional environments used for notebooks and manuscript figure generation are provided in `envs/`.

## Available case studies

| Case study       | Description                                  |
| ---------------- | -------------------------------------------- |
| `apl/`           | PLZF-RARα acute promyelocytic leukemia (APL) |
| `hematopoiesis/` | Early hematopoietic differentiation          |

See the corresponding README file in each directory for detailed reproduction instructions.

## Repository structure

```text
scbolt-case-studies/
├── envs/
├── apl/
└── hematopoiesis/
```
