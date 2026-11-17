"""Unicode tokenization, NLTK stemming and spaCy Russian lemmatization."""
import re
from functools import lru_cache
from nltk.stem.snowball import RussianStemmer
from .config import DATA
STOPWORDS=set((DATA/'russian_stopwords.txt').read_text().split())-{'не','нет','без'}
STEMMER=RussianStemmer()


def normalize(text):
    text=text.lower().replace('ё','е')
    text=re.sub(r'\b(?:айту|аиту)\b','aitu',text)
    text=re.sub(r'\bобщаг\w*','общежитие',text)
    return re.sub(r'\s+',' ',text).strip()


def tokens(text):
    return re.findall(r'[^\W_]+',normalize(text),flags=re.UNICODE)


@lru_cache(maxsize=1)
def nlp():
    import spacy
    pipeline=spacy.blank('ru')
    pipeline.add_pipe('lemmatizer',config={'mode':'pymorphy3'})
    pipeline.initialize()
    return pipeline


@lru_cache(maxsize=8192)
def preprocess(text,mode='lemma'):
    if mode=='lemma':
        words=[t.lemma_.lower() for t in nlp()(normalize(text)) if t.is_alpha or t.like_num]
    elif mode=='stem':words=[STEMMER.stem(t) for t in tokens(text)]
    elif mode=='raw':words=tokens(text)
    else:raise ValueError('Unknown preprocessing mode')
    return ' '.join(w for w in words if w not in STOPWORDS)
