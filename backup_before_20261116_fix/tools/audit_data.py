"""Reproduce cleaning audit without replacing stable benchmark identifiers."""
import json
import pandas as pd
from faq.config import ROOT,DATA


def main():
    raw=pd.read_parquet(DATA/'raw.parquet').fillna('');frame=raw.copy()
    for key in ['question','answer','raw_label']:
        frame[key]=frame[key].astype(str).str.replace(r'\s+',' ',regex=True).str.strip()
    empty=frame.question.eq('')|frame.answer.eq('')
    headers=frame.question.str.lower().eq('questions')&frame.answer.str.lower().eq('answers')
    valid=frame[~empty&~headers];duplicates=int(valid.duplicated(['question','answer']).sum())
    clean=valid.drop_duplicates(['question','answer']);conflicts=clean.groupby('question').answer.nunique()
    frozen=pd.read_parquet(DATA/'original_faq.parquet')
    summary={'raw_rows':len(raw),'empty_rows':int(empty.sum()),'header_rows':int(headers.sum()),'exact_duplicate_rows':duplicates,'clean_rows':len(clean),'conflicting_questions':int((conflicts>1).sum()),'frozen_rows':len(frozen),'clean_matches_frozen':set(zip(clean.question,clean.answer))==set(zip(frozen.question,frozen.answer))}
    (ROOT/'artifacts/data_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
    summary['snapshot_covers_all_questions']=set(clean.question)==set(frozen.question)
    summary['snapshot_answers_present_in_raw']=set(zip(frozen.question,frozen.answer))<=set(zip(clean.question,clean.answer))
    conflicts_out=[]
    for question in conflicts[conflicts>1].index:
        fid=int(frozen.loc[frozen.question.eq(question),'faq_id'].iloc[0])
        conflicts_out.append({'id':f'legacy-{fid:03}','question':question,'answers':clean.loc[clean.question.eq(question),'answer'].tolist(),'status':'unresolved'})
    (DATA/'conflicting_answers.json').write_text(json.dumps(conflicts_out,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'artifacts/data_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
    if not summary['snapshot_covers_all_questions'] or not summary['snapshot_answers_present_in_raw']:raise ValueError('Snapshot provenance mismatch')
    print(summary)

if __name__=='__main__':main()
