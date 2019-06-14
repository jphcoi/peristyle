import statistics
import csv
import json
import re
import nltk
import ural
import spacy
import numpy
import os
from nltk.tokenize import sent_tokenize
from ural import LRUTrie
from statistics import median
from statistics import mean
from statistics import stdev
from collections import defaultdict
from timeit import default_timer as timer
from multiprocessing import Pool



class Timer(object):
    def __init__(self, name="Timer"):
        self.name = name

    def __enter__(self):
        self.start = timer()

    def __exit__(self, *args):
        self.end = timer()
        self.duration = self.end - self.start
        print("%s:" % self.name, self.duration)


with Timer("load nlp"):
    nlp = spacy.load("fr_core_news_sm", disable=["textcat", "parser"])


HTML=re.compile(r"<[^>]*>")
USELESS=re.compile(r"[\"’`\- ]+")

POINT=re.compile(r"[!?.]+")
PUNCT=re.compile(r"[!?,;:_()\[\]«»—\"]|[.]+")
COMMA=re.compile(r",")
NOT_CHAR=re.compile(r"[.!?,;:\"\-\s\n\r_()\[\]«»’`/\"0-9]+")
CHAR=re.compile(r"[a-zéèà]")
NEGATION=re.compile(r"\bne\b|\bn'\b|\bnon\b", re.I)
SUBJ=re.compile(r"\bje\b|\bma\b|\bme\b|\bmon\b|\bmes\b|\bj'\b|\bm'\b|\bmien\b|\bmienne\b|\bmiens\b|\bmiennes\b", re.I)
INTERPEL=re.compile(r"\btu\b|\bt'\b|\bte\b|\btes\b|\bton\b|\bta\b|\btien\b|\btiens\b|\btienne\b|\btiennes\b|\bvous\b|\bvos\b|\bvotre\b|\bvôtre\b|\bvôtres\b", re.I)
NOUS=re.compile(r"\bnous\b|\bnos\b|\bnotre\b|\bnrôte\b|\bnôtres\b", re.I)
QUOTE=re.compile(r"[\"«»]")
BRACKET=re.compile(r"[(){}\[\]]")

PERSON=re.compile(r"Gender=[A-z]+\||Number=[A-z]+\||Person=.\|")


def generate_stopwords():
    with open("../nlp/stopwords_français.txt", "r") as f:
        stopwords={word.strip() for word in f.readlines()}
    return stopwords

def generate_dictionary():
    with open("../nlp/french.txt", "r") as f:
        dictionary={word.strip() for word in f.readlines()}
    return dictionary

def generate_language_level():
    wiktionaire=defaultdict(set)
    with open("../nlp/wikitionary.csv", "r") as f:
        reader=csv.DictReader(f)
        for row in reader:
            language_level=row["language_level"]
            word=row["word"]
            if language_level!="":
                 wiktionaire[language_level].add(word)
    return wiktionaire

def generate_proper_noun_exceptions():
    with open("../nlp/propernoun_exceptions.txt", "r") as f:
        propernoun_exceptions={name.strip() for name in f.readlines()}
    return propernoun_exceptions

STOPWORDS=generate_stopwords()
DICTIONARY=generate_dictionary()
LANGUAGE_LEVEL=generate_language_level()
PROPER_NOUN_EXCEPTIONS=generate_proper_noun_exceptions()

csv.field_size_limit(100000000)

def is_char(word):
    return not bool(NOT_CHAR.search(word))

def squeeze(txt): #pour être sur que le sent tokenizer de nltk marche bien
    txt=re.sub(r"[.]+", ".", txt)
    txt=re.sub(USELESS, " ", txt)
    return txt

def clean(txt):
    txt=re.sub(HTML, " ", txt)
    txt.strip()
    return txt


def generate_sources():

    f2=open("tables/sources.csv", "r")
    sources=csv.DictReader(f2)

    sources_list=[]

    for row in sources:
        source={"url": row["url"],
                "name":row["name"],
                "id":row["id"],
                "politics":row["politics"],
                "level0":row["level0_title"],
                "level1":row["level1_title"],
                "level2":row["level2_title"],
                "webentity":row["webentity"]}
        sources_list.append(source)

    f2.close()

    return sources_list



#def generate_linkingwords():

def get_language_level(language_level, word1, word2):
    for level in language_level.keys():
        if word1 in LANGUAGE_LEVEL[level] or word2 in LANGUAGE_LEVEL[level]:
            language_level[level]+=1
            return language_level
        else:
            language_level["level1"]+=1
            return language_level

def calcul_verb(verbs, nb_verbs):
    result={}

    nb_past_verbs=0
    nb_fut_verbs=0
    nb_pres_verbs=0
    nb_imp_verbs=0
    nb_conditional=0
    nb_other_verbs=0

    tenses=defaultdict(set)
    persons=defaultdict(int)

    for verb in verbs:

        if "Plur" in verb:
            persons["plur"]+=1
        elif "Sing" in verb:
            persons["sing"]+=1

        if "Mood=Cnd" in verb:
            nb_conditional+=1

        tens=re.sub(PERSON, "", verb)
        if "Pres" in tens:
            tenses["pres"].add(tens)
            nb_pres_verbs+=1
        elif "Past" in tens:
            tenses["past"].add(tens)
            nb_past_verbs+=1
        elif "Fut" in tens:
            tenses["fut"].add(tens)
            nb_fut_verbs+=1
        elif "Imp" in tens:
            tenses["imp"].add(tens)
            nb_imp_verbs+=1
        else:
            tenses["others"].add(tens)
            nb_other_verbs+=1


    verbs_diversity=0
    for tens in tenses:
        verbs_diversity+=len(tenses[tens])

    result={}

    if nb_verbs>0 and verbs_diversity>0:

        result["past_verb_cardinality"]=(len(tenses["past"])/verbs_diversity)
        result["pres_verb_cardinality"]=(len(tenses["pres"])/verbs_diversity)
        result["fut_verb_cardinality"]=(len(tenses["fut"])/verbs_diversity)
        result["imp_verb_cardinality"]=(len(tenses["imp"])/verbs_diversity)
        result["other_verb_cardinality"]=(len(tenses["others"])/verbs_diversity)

        result["past_verb_prop"]=(nb_past_verbs/nb_verbs)
        result["pres_verb_prop"]=(nb_pres_verbs/nb_verbs)
        result["fut_verb_prop"]=(nb_fut_verbs/nb_verbs)
        result["imp_verb_prop"]=(nb_imp_verbs/nb_verbs)

        result["plur_verb_prop"]=(persons["plur"]/nb_verbs)
        result["sing_verb_prop"]=(persons["sing"]/nb_verbs)

        result["conditional_prop"]=nb_conditional/nb_verbs
        result["verbs_diversity"]=(verbs_diversity/nb_verbs)


    else:
        result["past_verb_cardinality"]=0
        result["pres_verb_cardinality"]=0
        result["fut_verb_cardinality"]=0
        result["imp_verb_cardinality"]=0
        result["other_verb_cardinality"]=0

        result["past_verb_prop"]=0
        result["pres_verb_prop"]=0
        result["fut_verb_prop"]=0
        result["imp_verb_prop"]=0
        result["conditional_prop"]=0


        result["plur_verb_prop"]=0
        result["sing_verb_prop"]=0

        result["verbs_diversity"]=0

    return result

def calcul_punct(punctuations, nb_puncts, nb_tokens):
    nb_sent=0
    nb_quote=0
    nb_bracket=0
    nb_comma=0

    result={}

    for punct in punctuations.keys():
        if POINT.match(punct):
            nb_sent+=punctuations[punct]
        elif QUOTE.match(punct):
            nb_quote+=punctuations[punct]
        elif BRACKET.match(punct):
            nb_bracket+=punctuations[punct]
        elif COMMA.search(punct):
            nb_comma+=punctuations[punct]

    if nb_quote%2!=0 or nb_bracket%2!=0:
        if nb_quote%2!=0:
            nb_quote+=1
        else:
            nb_bracket+=1
    else:
        nb_quote=nb_quote/2
        nb_bracket=nb_bracket/2

    result={}
    question_prop=0
    exclamative_prop=0
    quote_prop=0
    bracket_prop=0
    comma_prop=0

    if nb_sent>0:
        question_prop=(punctuations["?"]/nb_sent)
        exclamative_prop=(punctuations["!"]/nb_sent)
        quote_prop=(nb_quote/nb_sent)
        bracket_prop=(nb_bracket/nb_sent)
        comma_prop=(nb_comma/nb_tokens)

    result["question_prop"]=question_prop
    result["exclamative_prop"]=exclamative_prop
    result["quote_prop"]=quote_prop
    result["bracket_prop"]=bracket_prop
    result["comma_prop"]=comma_prop
    return result

def calcul_sttr(voc_mean):
    sttr=0
    if voc_mean!=[]:
        sttr=sum(voc_mean)/len(voc_mean)
    return {"sttr":sttr}

def calcul_pos(pos_counting, nb_tokens):
    result={}

    if nb_tokens>0:
        result["noun_prop"]=pos_counting["NOUN"]/nb_tokens
        result["cconj_prop"]=pos_counting["CCONJ"]/nb_tokens
        result["adj_prop"]=pos_counting["ADJ"]/nb_tokens
        result["sconj_prop"]=pos_counting["SCONJ"]/nb_tokens
        result["verb_prop"]=(pos_counting["VERB"]+pos_counting["AUX"])/nb_tokens
        result["adv_prop"]=pos_counting["ADV"]/nb_tokens
    else:
        result["noun_prop"]=0
        result["cconj_prop"]=0
        result["sconj_prop"]=0
        result["adj_prop"]=0
        result["verb_prop"]=0
        result["adv_prop"]=0

    return result

def calcul_ner(txt, nb_tokens):
    nb_entities=len(txt.ents)
    entities={"PERSON":0, "NORP":0, "FAC":0, "ORG":0, "GPE":0, "LOC":0, "PRODUCT":0, "EVENT":0}

    for entity in txt.ents:
        label=entity.label_
        if label in entities.keys():
            entities[label]+=1

    result={"ner_prop": nb_entities/nb_tokens, "person_prop": entities["PERSON"]/nb_tokens, "norp_prop": entities["NORP"]/nb_tokens, "fac_prop": entities["FAC"]/nb_tokens, "org_prop": entities["ORG"]/nb_tokens, "gpe_prop": entities["GPE"]/nb_tokens, "loc_prop": entities["LOC"]/nb_tokens, "product_prop": entities["PRODUCT"]/nb_tokens, "event_prop": entities["EVENT"]/nb_tokens}
    return result


def pos_tagging(txt): #calcule certaines features en utilisant le pos tagging : temps (cardinalité temps), pos, punct, negation(marche pas top)

    txt=str(txt)
    with Timer("nlp"):
        txt = nlp(txt)

    pos_counting=defaultdict(int)
    negation=defaultdict(int)
    punctuations=defaultdict(int)
    verbs=[]

    nb_propernoun=0
    nb_dictwords=0
    voc_mean=[]
    voc_counter=0
    voc=set()
    nb_word=0
    nb_numbers=0
    nb_pronp=0
    language_level={"level0":0, "level1":0, "level2":0, "autre":0}

    for token in txt:
        print(token)
        pos_counting[token.pos_]+=1
        language_level=get_language_level(language_level, token.lemma_, token.text)
        if "PUNCT" not in token.pos_ and "SPACE" not in token.pos_:
            nb_word+=1

            if token.text.istitle():
                if token.lemma_.lower() not in DICTIONARY and token.text.lower() not in DICTIONARY or token.text in PROPER_NOUN_EXCEPTIONS:
                    nb_propernoun+=1

            if token.lemma_.lower() in DICTIONARY or token.text.lower() in DICTIONARY:
                voc_counter+=1
                voc.add(token.text)
                nb_dictwords+=1

        if voc_counter==100:
            voc_mean.append((len(voc)/voc_counter))
            voc.clear()
            voc_counter=0

        if "PUNCT" in token.pos_:
            punctuations[token.text]+=1

        elif "NUM" in token.pos_:
            nb_numbers+=1

        elif "VERB" in token.pos_ or "AUX" in token.pos_:
           verbs.append(token.tag_)

        elif "PRON" in token.pos_ and "PronType=Prs" in token.tag_:
            nb_pronp+=1

    verbs_results={}
    punctuation_results={}
    pos_results={}

    punctuation_results=calcul_punct(punctuations, pos_counting["PUNCT"], len(txt))
    pos_results=calcul_pos(pos_counting,len(txt))
    sttr=calcul_sttr(voc_mean)

    verbs_results=calcul_verb(verbs, pos_counting["VERB"]+pos_counting["AUX"])
    ner_results=calcul_ner(txt, len(txt))
    results={}

    results.update(verbs_results)
    results.update(punctuation_results)
    results.update(pos_results)
    results.update(sttr)

    results["dictwords_prop"]=nb_dictwords/nb_word
    results["proper_noun_prop"]=nb_propernoun/nb_word
    results["nb_word"]=nb_word
    results["numbers_prop"]=nb_numbers/len(txt)
    results["pronp_prop"]=nb_pronp/len(txt)
    results["level0_prop"]=language_level["level0"]/nb_word
    results["level1_prop"]=language_level["level1"]/nb_word
    results["level2_prop"]=language_level["level2"]/nb_word
    results["autre_prop"]=language_level["autre"]/nb_word

    results.update(ner_results)
    return results


## Pour les trucs avec re.match

def count_interpellation(txt, nb_word, nb_sent) :
    interpellations=re.findall(INTERPEL, txt)
    interpellation_prop1=0
    interpellation_prop2=0
    if nb_word>0 and nb_sent>0:
        interpellation_prop1=len(interpellations)/nb_word
        interpellation_prop2=len(interpellations)/nb_sent
    return {"interpellation_prop1":interpellation_prop1, "interpellation_prop2":interpellation_prop2}

def count_nous(txt, nb_word, nb_sent) :
    nous=re.findall(NOUS, txt)
    nous_prop1=0
    nous_prop2=0
    if nb_word>0 and nb_sent>0:
        nous_prop1=len(nous)/nb_word
        nous_prop2=len(nous)/nb_sent
    return {"nous_prop1":nous_prop1, "nous_prop2":nous_prop2}


def count_subjectivity(txt, nb_word, nb_sent):
    subjectivities=re.findall(SUBJ, txt)
    subjectivity_prop1=0
    subjectivity_prop2=0
    if nb_word>0 and nb_sent>0:
        subjectivity_prop1=len(subjectivities)/nb_word
        subjectivity_prop2=len(subjectivities)/nb_sent
    return {"subjectivity_prop1":subjectivity_prop1, "subjectivity_prop2":subjectivity_prop2}

def count_negation(txt, nb_word, nb_sent):
    negations=re.findall(NEGATION, txt)
    negation_prop1=0
    negation_prop2=0
    if nb_word>0 and nb_sent>0:
        negation_prop1=len(negations)/nb_word
        negation_prop2=len(negations)/nb_sent
    return {"negation_prop1":negation_prop1, "negation_prop2":negation_prop2}

##Pour utiliser NLTK

def count_letters(letters, word):
    elaouin=["e","l","o","a","i","n"]
    for char in word:
        char=char.lower()
        if char in elaouin:
            letters[char]+=1

    return letters

"""
def calcul_letters(letters, nb_char):
    for letter in letters.keys():
        if nb_char>0:
            letters[letter]=(letters[letter]/nb_char)
        else:
            letters[letter]=0
    return letters
"""

def calcul_voc(types, nb_word):
    voc_diversity=0
    if nb_word!=0:
        voc_diversity+=1
        #voc_diversity=types/(numpy.log(int(nb_word)))[0]
    return voc_diversity



def calcul_ARI(txt): # on pourrait faire tout dans l"un à condition d"abandonner la médiane du nb de mots par phrase

    txt=squeeze(txt)
    sentences=nltk.tokenize.sent_tokenize(txt, language="french")
    txt=[nltk.word_tokenize(sentence) for sentence in sentences]

    ARI=0.0
    nb_char=0
    nb_word=0
    nb_sentence=0
    TYPE=""
    nb_dictwords=0
    nb_shortwords=0
    nb_longwords=0
    nb_stopwords=0
    letters={"e":0,"l":0,"o":0,"a":0,"i":0,"n":0}
    voc=defaultdict(int)
    max_len_word=0

    mean_cw=0
    mean_ws=0
    median_cw=0
    median_ws=0
    shortwords_prop=0
    longwords_prop=0



    nb_cw=[] # cw => char per word
    nb_ws=[] # ws => word per sent

    for sentence in txt:

        if len(sentence)>3 and len(sentence)<300:
            nb_sentence+=1
            for word in sentence:
                if is_char(word):
                    if len(word)<50:
                        nb_word+=1
                        word=word.lower()

                        nb_word+=1
                        nb_char+=len(word)
                        nb_cw.append(len(word))

                        if nb_char<100:
                            letters=count_letters(letters, word)

                        if len(word)<5:
                            nb_shortwords+=1

                        if len(word)>5:
                            nb_longwords+=1

                        if word in STOPWORDS:
                            nb_stopwords+=1


                nb_ws.append(len(sentence))


    if nb_word>0 and nb_sentence>3:

        mean_cw=nb_char/nb_word
        mean_ws=nb_word/nb_sentence

        median_cw=median(nb_cw)
        median_ws=median(nb_ws)

        shortwords_prop=(nb_shortwords/nb_word)
        longwords_prop=(nb_longwords/nb_word)

        max_len_word=max(nb_cw)
        ARI=4.71*(mean_cw)+0.5*(mean_ws)-21.43

        if ARI<0 or 30<ARI:
            ARI=0

    result={
        "ARI":ARI ,
        "nb_sent":nb_sentence,
        "nb_char":nb_char,
        "mean_cw":mean_cw,
        "mean_ws":mean_ws,
        "median_cw":median_cw,
        "median_ws":median_ws,
        "max_len_word":max_len_word,
        "shortwords_prop":shortwords_prop,
        "longwords_prop":longwords_prop
        }

    #if nb_char>0:
        #result.update(calcul_letters(letters, nb_char))
    result.update({"a":letters["a"], "e":letters["e"], "l":letters["l"], "o":letters["o"], "i":letters["i"], "n":letters["n"]})

    return result



def calcul_features(path):
    row=path[1]
    results={key:row[key] for key in row.keys()}

    try:
        with open (path[0],"r") as ft:
            txt=ft.read()

    except:
        print("opening failed")
        return False

    results={}
    txt=clean(txt)
    results.update(pos_tagging(txt))
    results.update(calcul_ARI(txt))
    results.update(count_negation(txt,results["nb_word"], results["nb_sent"]))
    results.update(count_interpellation(txt, results["nb_word"], results["nb_sent"]))
    results.update(count_nous(txt, results["nb_word"], results["nb_sent"]))
    results.update(count_subjectivity(txt, results["nb_word"],  results["nb_sent"]))

    return results

def calcul_features_id(story):

    with open ("testing_stories/sample/" + story,"r") as ft:
        txt = ft.read()

    results={}
    txt=clean(txt)
    results.update(pos_tagging(txt))
    results.update(calcul_ARI(txt))
    results.update(count_negation(txt,results["nb_word"], results["nb_sent"]))
    results.update(count_interpellation(txt, results["nb_word"], results["nb_sent"]))
    results.update(count_nous(txt, results["nb_word"], results["nb_sent"]))
    results.update(count_subjectivity(txt, results["nb_word"],  results["nb_sent"]))
    return results



##### Fonction pour calculer les nouvelles features sur tous les textes et les enregistrées

def generate_path(row):
    story_id=row["stories_id"]
    return "sample/"+story_id+".txt"

def generator():
    fs=open("tables/sample_normalized_sorted.csv", "r")
    reader=csv.DictReader(fs)
    i=0
    for row in reader:
        print(row["stories_id"])
        yield (generate_path(row), row)


def find_media_info(sources, media_id, info="level0"):
    for source in sources:
        if source["id"]==media_id:
            return source
    return False


def ajout_info():

    with open("tables/sample_normalized_sorted.csv", "r") as fs:
        reader=csv.DictReader(fs)
        reader.fieldnames+=["ARI", "nb_sent", "nb_word", "nb_char", "mean_cw", "mean_ws", "median_cw", "median_ws", "shortwords_prop" , "longwords_prop" ,"max_len_word", "dictwords_prop", "proper_noun_prop", "negation_prop1", "negation_prop2", "subjectivity_prop1", "subjectivity_prop2", "interpellation_prop1", "interpellation_prop2", "nous_prop1", "nous_prop2", "verb_prop", "past_verb_cardinality", "pres_verb_cardinality", "fut_verb_cardinality", "imp_verb_cardinality", "other_verb_cardinality","past_verb_prop", "pres_verb_prop", "fut_verb_prop","imp_verb_prop", "plur_verb_prop","sing_verb_prop","verbs_diversity", "conditional_prop","question_prop","exclamative_prop","quote_prop","bracket_prop","noun_prop","cconj_prop", "sconj_prop", "pronp_prop", "adj_prop","adv_prop", "a", "e", "i", "l", "n", "o", "sttr", "comma_prop", "numbers_prop", "level0_prop", "level1_prop", "level2_prop", "autre_prop", "ner_prop", "person_prop", "norp_prop", "fac_prop", "org_prop", "gpe_prop", "loc_prop", "product_prop", "event_prop" ]

    fd=open("tables/sample_with_features.csv", "w")
    writer=csv.DictWriter(fd, fieldnames=reader.fieldnames)
    writer.writeheader()
    times=[]

    i=0
    with Timer("multiprocessing babe"):
        with Pool(4) as pool:
            for features in pool.imap_unordered(calcul_features, generator()):
                if features!={}:
                    writer.writerow(features)

    fd.close()
    fs.close()

    return 0

def add_other_stories():
    fd = open("testing_stories/testing_stories_features.csv", "w")
    fieldnames = ["story" ,"ARI", "nb_sent", "nb_word", "nb_char", "mean_cw", "mean_ws", "median_cw", "median_ws", "shortwords_prop" , "longwords_prop" ,"max_len_word", "dictwords_prop", "proper_noun_prop", "negation_prop1", "negation_prop2", "subjectivity_prop1", "subjectivity_prop2", "interpellation_prop1", "interpellation_prop2", "nous_prop1", "nous_prop2", "verb_prop", "past_verb_cardinality", "pres_verb_cardinality", "fut_verb_cardinality", "imp_verb_cardinality", "other_verb_cardinality","past_verb_prop", "pres_verb_prop", "fut_verb_prop","imp_verb_prop", "plur_verb_prop","sing_verb_prop","verbs_diversity", "conditional_prop","question_prop","exclamative_prop","quote_prop","bracket_prop","noun_prop","cconj_prop", "sconj_prop", "pronp_prop", "adj_prop","adv_prop", "a", "e", "i", "l", "n", "o", "sttr", "comma_prop", "numbers_prop", "level0_prop", "level1_prop", "level2_prop", "autre_prop", "ner_prop", "person_prop", "norp_prop", "fac_prop", "org_prop", "gpe_prop", "loc_prop", "product_prop", "event_prop" ]
    writer = csv.DictWriter(fd, fieldnames = fieldnames)
    writer.writeheader()

    for story in os.listdir('./testing_stories/sample'):
        print(story)
        result = calcul_features_id(story)
        result["story"] = story[:-4]


        if result["ARI"] <30 and 0<result["ARI"] and result["nb_word"] != 0 and result["nb_sent"] <= 3 and result["nb_word"]>250 and 1500>result["nb_word"]:
            writer.writerow(result)

    fd.close()
    return 'YOOOO'

add_other_stories()




#### Bonjor on travaille ####

#ajout_info()
