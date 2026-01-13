#!/usr/bin/env Rscript
#
# scType standalone runner
#
# Usage examples:
#   Rscript celltypeAppAgent/tools/r/sctype_run.R \
#       --data=../.agentype_cache/data_20250911_224809.h5 \
#       --tissue="Immune system" \
#       --out=./sctype_result.json
#
#   Rscript celltypeAppAgent/tools/r/sctype_run.R \
#       --data=../data.rds --tissue=Blood --out=./out.json
#
# Optional flags:
#   --wrapper=/path/to/sctype_wrapper.R   # Prefer local wrapper file
#   --skip-install=1                      # Do not attempt to install packages
#

suppressWarnings(suppressMessages({
  # No package dependencies for argument parsing; use base R only
}))

cat("=== scType standalone runner ===\n")

# -------------------------
# Argument parsing helpers
# -------------------------
args <- commandArgs(trailingOnly = TRUE)
kv <- list()
for (a in args) {
  if (grepl("^--[A-Za-z_-]+=", a)) {
    key <- sub("^--([A-Za-z_-]+)=.*$", "\\1", a)
    val <- sub("^--[A-Za-z_-]+=", "", a)
    kv[[key]] <- val
  }
}

get_arg <- function(name, default = NULL) {
  if (!is.null(kv[[name]])) return(kv[[name]])
  default
}

data_path <- get_arg("data")
tissue    <- get_arg("tissue", "Immune system")
out_path  <- get_arg("out",   NULL)
wrapper   <- get_arg("wrapper", NULL)
skip_install <- isTRUE(tolower(get_arg("skip-install", "0")) %in% c("1","true","yes"))

if (is.null(data_path) || nchar(data_path) == 0) {
  stop("Missing required argument: --data=<path to .rds or easySCF .h5>")
}

data_path <- normalizePath(data_path, mustWork = FALSE)
cat("Input:", data_path, "\n")
cat("Tissue:", tissue, "\n")
if (!is.null(wrapper)) cat("Wrapper:", wrapper, "\n")
cat("Skip install:", skip_install, "\n")

if (!file.exists(data_path)) {
  stop(paste("File not found:", data_path))
}

ext <- tolower(tools::file_ext(data_path))
if (ext == "h5ad") {
  stop(".h5ad is not supported by scType. Convert to .rds or easySCF .h5")
}
if (!ext %in% c("rds", "h5")) {
  stop(paste("Unsupported extension:", ext, "(expected .rds or .h5)"))
}

# -------------------------
# Package helpers
# -------------------------
ensure_pkg <- function(pkg) {
  if (suppressWarnings(require(pkg, character.only = TRUE, quietly = TRUE))) return(invisible(TRUE))
  if (skip_install) stop(paste0("Package '", pkg, "' not installed and --skip-install=1 set"))
  cat("Installing package:", pkg, "\n")
  install.packages(pkg, repos = "https://cloud.r-project.org", quiet = TRUE)
  if (!suppressWarnings(require(pkg, character.only = TRUE, quietly = TRUE))) {
    stop(paste0("Failed to install package '", pkg, "'"))
  }
  invisible(TRUE)
}

ensure_devtools <- function() {
  if (suppressWarnings(require("devtools", quietly = TRUE))) return(invisible(TRUE))
  if (skip_install) stop("Package 'devtools' not installed and --skip-install=1 set")
  cat("Installing devtools...\n")
  install.packages("devtools", repos = "https://cloud.r-project.org", quiet = TRUE)
  if (!suppressWarnings(require("devtools", quietly = TRUE))) stop("Failed to install devtools")
  invisible(TRUE)
}

ensure_easySCFr <- function() {
  if (suppressWarnings(require("easySCFr", quietly = TRUE))) return(invisible(TRUE))
  if (skip_install) stop("Package 'easySCFr' not installed and --skip-install=1 set")
  ensure_devtools()
  cat("Installing easySCFr from GitHub (xleizi/easySCF/r)...\n")
  devtools::install_github("xleizi/easySCF/r", quiet = TRUE)
  if (!suppressWarnings(require("easySCFr", quietly = TRUE))) stop("Failed to install easySCFr")
  invisible(TRUE)
}

# -------------------------
# Load required packages
# -------------------------
ensure_pkg("dplyr")
ensure_pkg("Seurat")
ensure_pkg("jsonlite")
ensure_pkg("HGNChelper")

# -------------------------
# Load data
# -------------------------
cat("Loading data...\n")
sce <- NULL
if (ext == "h5") {
  # Load easySCF H5 via easySCFr
  ensure_easySCFr()
  sce <- easySCFr::loadH5(data_path)
  cat("Loaded easySCF .h5 data\n")
} else if (ext == "rds") {
  # Load Seurat RDS directly
  sce <- readRDS(data_path)
  cat("Loaded Seurat .rds data\n")
} else {
  stop("Unsupported extension after previous checks")
}

# -------------------------
# Load sctype_wrapper.R
# -------------------------
sctype_loaded <- FALSE
if (!is.null(wrapper) && file.exists(wrapper)) {
  cat("Sourcing local wrapper:", wrapper, "\n")
  tryCatch({
    source(wrapper)
    sctype_loaded <- TRUE
  }, error = function(e) {
    cat("Local wrapper failed:", e$message, "\n")
  })
}

if (!sctype_loaded) {
  cat("Trying remote sctype_wrapper.R (GitHub)...\n")
  tryCatch({
    source("https://raw.githubusercontent.com/kris-nader/sc-type/master/R/sctype_wrapper.R")
    sctype_loaded <- TRUE
    cat("Loaded wrapper from GitHub\n")
  }, error = function(e) {
    cat("GitHub failed, trying backup...\n")
    tryCatch({
      source("https://agent.s1f.ren/d/files/rds/sctype/R/sctype_wrapper.R")
      sctype_loaded <- TRUE
      cat("Loaded wrapper from backup URL\n")
    }, error = function(e2) {
      cat("Backup wrapper failed:", e2$message, "\n")
    })
  })
}

# -------------------------
# Run scType or fallback
# -------------------------
if (!sctype_loaded) {
  cat("Wrapper not loaded; using fallback: set sctype_celltype <- Idents(sce)\n")
  sce@meta.data$sctype_celltype <- as.character(Seurat::Idents(sce))
} else {
  cat("Running scType with tissue:", tissue, "\n")
  tryCatch({
    sce <- run_sctype(
      sce,
      known_tissue_type = tissue,
      name = "sctype_celltype",
      plot = FALSE
    )
    cat("scType completed\n")
  }, error = function(e) {
    cat("scType run failed, retry by reloading backup wrapper: ", e$message, "\n")
    sctype_loaded2 <- FALSE
    tryCatch({
      source("https://agent.s1f.ren/d/files/rds/sctype/R/sctype_wrapper.R")
      sctype_loaded2 <- TRUE
      cat("Re-sourced wrapper from backup URL\n")
    }, error = function(e2) {
      cat("Backup reload failed:", e2$message, "\n")
    })
    if (isTRUE(sctype_loaded2)) {
      cat("Retrying scType...\n")
      tryCatch({
        sce <- run_sctype(
          sce,
          known_tissue_type = tissue,
          name = "sctype_celltype",
          plot = FALSE
        )
        cat("scType completed\n")
      }, error = function(e3) {
        cat("Second scType attempt failed; using fallback sctype_celltype <- Idents(sce)\n")
        sce@meta.data$sctype_celltype <- as.character(Seurat::Idents(sce))
      })
    } else {
      cat("Could not reload wrapper; using fallback sctype_celltype <- Idents(sce)\n")
      sce@meta.data$sctype_celltype <- as.character(Seurat::Idents(sce))
    }
  })
}

# -------------------------
# Summarize clusters
# -------------------------
cat("Collecting cluster summaries...\n")
clusters <- levels(Seurat::Idents(sce))
cat("Clusters detected:", paste(clusters, collapse = ", "), "\n")

cluster_annotations <- list()
for (cluster in clusters) {
  cluster_cells_idx <- which(Seurat::Idents(sce) == cluster)
  if (length(cluster_cells_idx) > 0) {
    cluster_celltypes <- sce@meta.data$sctype_celltype[cluster_cells_idx]
    celltype_table <- table(cluster_celltypes)
    dominant_celltype <- names(celltype_table)[which.max(celltype_table)]
    max_count <- max(celltype_table)
    total_count <- length(cluster_cells_idx)
    proportion <- max_count / total_count

    if ("sctype_scores" %in% colnames(sce@meta.data)) {
      cluster_confidence <- mean(sce@meta.data$sctype_scores[cluster_cells_idx], na.rm = TRUE)
    } else {
      cluster_confidence <- proportion
    }

    cluster_annotations[[paste0("cluster", as.character(cluster))]] <- list(
      celltype   = dominant_celltype,
      confidence = round(cluster_confidence, 4),
      cell_count = max_count,
      total_cells = total_count,
      proportion = round(proportion, 4),
      all_celltypes = as.list(celltype_table)
    )
  }
}

result <- list(
  cluster_annotations = cluster_annotations,
  total_clusters = length(clusters),
  tissue_type = tissue,
  annotation_date = as.character(Sys.Date()),
  input_file = data_path,
  cluster_column = "seurat_clusters",
  total_cells = ncol(sce)
)

if (is.null(out_path) || nchar(out_path) == 0) {
  ts <- format(Sys.time(), "%Y%m%d_%H%M%S")
  out_path <- file.path(getwd(), paste0("sctype_annotation_result_", ts, ".json"))
}

out_dir <- dirname(out_path)
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

jsonlite::write_json(result, out_path, pretty = TRUE, auto_unbox = TRUE)
cat("Result saved to:", out_path, "\n")
