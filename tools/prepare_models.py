"""Download pinned model files only; never execute remote repository code."""
from huggingface_hub import snapshot_download
from faq.config import EMBED_MODEL,EMBED_REVISION,RERANK_MODEL,RERANK_REVISION


def prepare():
    for name,revision in [(EMBED_MODEL,EMBED_REVISION),(RERANK_MODEL,RERANK_REVISION)]:
        print('Модель:',name,flush=True)
        snapshot_download(name,revision=revision,allow_patterns=['*.json','*.safetensors','*.txt','*.model','*.vocab'],ignore_patterns=['onnx/*','openvino/*'])

if __name__=='__main__':prepare()
