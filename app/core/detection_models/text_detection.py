import re
from collections import defaultdict

import spacy

def initalize_pos_model(state=False):
    global MODEL_SPACY
    if state:
        MODEL_SPACY = spacy.load("en_core_web_sm")


def is_grammatically_sentence(sentence, verbs=1, nouns=2) -> bool:
    # From a Dependency-POV a sentence consists at least from a ROOT a Subj and a Obj.
    # From a Gramatical-POV a sentence consists at least from a Verb and two Nouns (one for the Obj, and one for the Obj).
    sentence = sentence.lstrip()
    sentence = sentence.rstrip()
    sentence = re.sub(" +", " ", sentence)
    if len(sentence) < 1: return False
    try:
        for token in MODEL_SPACY(sentence):
            if token.pos_ in ["VERB", "AUX"] and token.dep_ == "ROOT": verbs -= 1
            if token.pos_ in ["NOUN", "PROPN", "PRON"] and token.dep_ in ["nsubj", "csubj", "nsubjpass"]: nouns -= 1
            if token.pos_ in ["NOUN", "PROPN", "PRON"] and token.dep_ in ["dobj", "pobj"]: nouns -= 1
    except UnicodeEncodeError:
        return False
    if verbs < 1 and nouns < 1:
        return True
    else:
        return False


def get_type_frequency(text):
    numberOfWords = 0
    typesOfWord = defaultdict(int)
    try:
        for num, token in enumerate(MODEL_SPACY(text)):
            tokenType = _get_token_type(token)
            typesOfWord[tokenType] += 1
            numberOfWords = num
    except UnicodeEncodeError:
        tokenType = "Unknown"
        typesOfWord[tokenType] = 1
    typesOfWord = [(typ, count) for typ, count in typesOfWord.items()]
    typesOfWord.sort(key=lambda x: x[1], reverse=True)
    return numberOfWords, typesOfWord

def _get_token_type(token):
    if token.text in ['N/A', '-', ' - ', '/', "."] or len(token.text) < 3:
        return "UNKNOWN"
    if token.pos_ == "NUM":
        return "NUM"
    else:
        return "WORD"