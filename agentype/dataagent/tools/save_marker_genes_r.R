# Simple R function to convert FindAllMarkers to JSON
# Required: jsonlite package

#' Convert FindAllMarkers results to JSON format (simple version)
#' 
#' @param alm data.frame, FindAllMarkers output
#' @param output_file character, JSON file path
#' @param pval_threshold numeric, p-value threshold (default 0.05)
#' @return list of cluster genes
save_markers_to_json <- function(alm, output_file = "cluster_markers.json", pval_threshold = 0.05) {
  
  # Install jsonlite if needed
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    install.packages("jsonlite")
  }
  
  # Filter significant genes
  significant_alm <- alm[alm$p_val_adj < pval_threshold, ]
  
  # Split genes by cluster (the simple way!)
  cluster_to_genes <- split(as.character(significant_alm$gene), significant_alm$cluster)
  
  # Rename clusters to match required format
  names(cluster_to_genes) <- paste0("cluster", names(cluster_to_genes))
  
  # Save as JSON
  jsonlite::write_json(cluster_to_genes, output_file, pretty = TRUE, auto_unbox = FALSE)
  
  return(cluster_to_genes)
}
