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
OMNIPATH_VERSION = 2025-08-13
HCOP_VERSION = bundled
DOROTHEA_API = legacy
DOROTHEA_COMPATIBILITY = true
DOROTHEA_LEVELS = A

##############################
### Module-specific inputs ###
##############################

### hvg ###
ANALYSIS_HVG_FLAVOR = seurat_v3
ANALYSIS_HVG_TOP = 2000

### filtering ###
MAD_DEVIATION = 3 2

### clustering ###
DIM_PCA = 15
DIM_CLUSTERING = 15
NEIGHBORS = 10
RESOLUTION = 0.38
MIN_DIST = 0.5
SPREAD = 2.0

### annotation ###
LABEL = Prom1 Prom2 Rep Cycl Neu Alt

### knnsc ###
KNNSC_CENTRALITY_CTRL = Prom1 Prom2
KNNSC_PERIPHERY_CTRL = Rep Neu Alt
KNNSC_CENTRALITY_TREATED = Prom1 Prom2
KNNSC_PERIPHERY_TREATED = Rep Neu

### macrostates ###
MACROSTATE_METHOD = knnsc

### bin-cells ###
ZEROES_ARE_ZEROES = false

### bn-submin ###
MIN_SELF_LOOP_INFER = true
INFER_LIMIT = 100
