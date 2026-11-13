"""One serialized UTF-8 payload budget. chars/4 is an estimate, not exact tokens."""
from dataclasses import dataclass
import math
from .contracts import canonical


class BudgetError(ValueError): pass


@dataclass(frozen=True)
class Budget:
    max_bytes: int=8000
    max_chars: int=6000
    estimated_tokens: int | None=None

    def __post_init__(self):
        for value in (self.max_bytes,self.max_chars):
            if type(value) is not int or value<1: raise ValueError('positive integer budget required')
        if self.estimated_tokens is not None and (type(self.estimated_tokens) is not int or self.estimated_tokens<1): raise ValueError('invalid token estimate budget')

    def fits(self,payload):
        chars=len(payload);size=len(payload.encode('utf-8'))
        return size<=self.max_bytes and chars<=self.max_chars and (self.estimated_tokens is None or math.ceil(chars/4)<=self.estimated_tokens)


def pack(header,bundles,budget,*,required=()):
    """Indivisible citation/conflict bundles; omitted content is never silently clipped."""
    required=set(required);selected=[];omitted=[]
    def render(items,omission_count):
        return canonical({**header,'items':items,'omitted_units':omission_count,'truncated':bool(omission_count)})
    # Reserve the worst possible omission-count digits from the beginning.
    if not budget.fits(render([],sum(len(b) for b in bundles))): raise BudgetError('BUDGET_TOO_SMALL: required snapshot/freshness metadata cannot fit')
    ordered=sorted(enumerate(bundles),key=lambda pair:(not any(i['id'] in required for i in pair[1]),pair[0]))
    for _,bundle in ordered:
        ids={item['id'] for item in bundle}
        if budget.fits(render(selected+bundle,sum(len(b) for b in bundles))): selected+=bundle
        elif ids & required: raise BudgetError('REQUIRED_CONTENT_CANNOT_FIT: '+','.join(sorted(ids & required)))
        else: omitted.extend({'id':i['id'],'reason':'total_payload_budget'} for i in bundle)
    ids={i['id'] for i in selected}
    if not required<=ids: raise BudgetError('REQUIRED_CONTENT_UNAVAILABLE: '+','.join(sorted(required-ids)))
    payload=render(selected,len(omitted))
    if not budget.fits(payload): raise BudgetError('BUDGET_TOO_SMALL: final accounting failed')
    return {'payload':payload,'diagnostics':{'selected_ids':[i['id'] for i in selected],'omissions':omitted,
            'bytes':len(payload.encode()),'characters':len(payload),'estimated_tokens':math.ceil(len(payload)/4),
            'token_accounting':'ceil(Unicode codepoints/4); heuristic, not exact; no target tokenizer pinned',
            'exact_tokens':None,'max_bytes':budget.max_bytes,'max_chars':budget.max_chars}}
