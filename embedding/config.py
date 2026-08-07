MODEL_NAME = "BAAI/bge-m3"

TEXT_FIELD = "embedding_text"

BATCH_SIZE = 8
MAX_LENGTH = 8192

USE_FP16 = True
REQUIRE_CUDA = True
DEVICE_INDEX = 0

NORMALIZE_EMBEDDINGS = True

EMBEDDINGS_FILENAME = "embeddings.npy"
METADATA_FILENAME = "metadata.json"
REPORT_FILENAME = "embedding_report.json"