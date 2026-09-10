########################
### Project settings ###
########################

ORGANISM = mouse
CONDITIONS = ctrl treated
PROJECT_DIR = project_gsm

#####################
### Input sources ###
#####################

GSM_CTRL = GSM5492245
GSM_TREATED = GSM5492246

##########################
### External resources ###
##########################

GENEINFO_VERSION = bundled
PRIOR_KNOWLEDGE = dorothea
DOROTHEA_API = modern
DOROTHEA_LEVELS = A B
#DOROTHEA_API = legacy
#DOROTHEA_LEVELS = A
DOROTHEA_COMPATIBILITY = true
OMNIPATH_VERSION = 2025-08-13
HCOP_VERSION = bundled

##############################
### Module-specific inputs ###
##############################

### hvg ###
OMICS_HVG_METHOD = loess
OMICS_HVG_TOP = 2000

### filtering ###
MAD_DEVIATION = 3 2
MT = 0.30

### clustering ###
DIM_PCA = 15
#NEIGHBORS = 10
#RESOLUTION = 0.38
NEIGHBORS = 14
RESOLUTION = 0.4
MIN_DIST = 0.5
SPREAD = 2.0

### annotation ###
LABEL = Prom1 Prom2 Rep Cycl Neu Alt

### macrostates ###
MACROSTATE_METHOD = knnsc
KNNSC_CENTRALITY_CTRL = Prom1 Prom2
KNNSC_PERIPHERY_CTRL = Rep Neu Alt
KNNSC_CENTRALITY_TREATED = Prom1 Prom2
KNNSC_PERIPHERY_TREATED = Rep Neu

BIN_HVG_METHOD = binning
BIN_HVG_TOP =
#BIN_INCLUDE_NODES = \
#	Rara Rarb Zbtb16 Cebpe Cebpa Spi1 Myc Skp2 Ccna2 Mdm2 E2f1 Ccnd1 \
#	Cdk2 Cdk4 Cdk6 Pcna Pim1 Cdkn2d Rb1 Cdkn1a Cdkn1b Trp53 Bax Ezh2 \
#	Nfkb1 Traf1 Ddit4 Ppp1r15a Epx Alox15 Prg3 Ear6 S100a8 S100a9 Ly6g Ngp Usp37

### bin-cells ###
ZEROES_ARE_ZEROES = false

### inference ###
MAX_CLAUSES = 4

CLAUSE_CONTINUATION_SOFT = true
DOMAIN_CONTINUATION_SOFT = true
CLINGO_MODE_SOFT = opt
CLINGO_STRATEGY_SOFT = bb,inc

TIMEOUT_SOFT = 5h
TIMEOUT_RELAXED = 5h
TIMEOUT_SEED = 5h

### bn-submin ###
MIN_SELF_LOOP_INFER = true
INFER_LIMIT = 10000

DOMAIN_CONTINUATION_RELAXED = false
TIMEOUT_LOCK = 0

####### TMP ########

#CLINGO_MODE_SEED = opt
#CLINGO_STRATEGY_SEED = bb,inc
#JOBS_RELAXED = 1
