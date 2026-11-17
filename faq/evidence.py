"""Conservative comparison of answer variants; never erase numbers or negation."""
import re
import unicodedata


def canonical_answer(text):
    text=unicodedata.normalize('NFKC',text).strip()
    pairs={'"':'"',"'":"'",'«':'»','“':'”'}
    while len(text)>1 and text[0] in pairs and text[-1]==pairs[text[0]]:
        text=text[1:-1].strip()
    return re.sub(r'\s+',' ',text)


def conflicting_answers(answers):
    return len({canonical_answer(a) for a in answers})>1
