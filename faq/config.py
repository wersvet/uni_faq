from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
DB=DATA/'university.sqlite3'
EMBED_MODEL='intfloat/multilingual-e5-base'
EMBED_REVISION='d128750597153bb5987e10b1c3493a34e5a4502a'
RERANK_MODEL='cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'
RERANK_REVISION='1427fd652930e4ba29e8149678df786c240d8825'
