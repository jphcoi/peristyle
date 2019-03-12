import statistics
import csv
import json
import re
import nltk
import ural
import spacy
from nltk.tokenize import sent_tokenize
from ural import LRUTrie
from statistics import median
from statistics import mean
from collections import defaultdict
from timeit import default_timer as timer
from multiprocessing import Pool


class Timer(object):
    def __init__(self, name='Timer'):
        self.name = name

    def __enter__(self):
        self.start = timer()

    def __exit__(self, *args):
        self.end = timer()
        self.duration = self.end - self.start
        print('%s:' % self.name, self.duration)


with Timer('load nlp'):
    nlp = spacy.load('fr_core_news_sm', disable=['textcat', 'parser'])


HTML=re.compile(r'<[^>]*>')
VIDE=re.compile(r'[\s\n\t\r]+')
USELESS=re.compile(r'[\'’`\- ]+')

POINT=re.compile(r'[!?.]+')
PUNCT=re.compile(r'[!?,;:_()\[\]«»—"]|[.]+')
NOT_CHAR=re.compile(r'[.!?,;:\'\-\s\n\r_()\[\]«»’`/"0-9]+')
CHAR=re.compile(r'[a-zéèà]')
NEGATION=re.compile(r'\b[Nn][e\'on ]{1,2}\b')
SUBJ=re.compile(r'\b[Jj]e\b|\b[Mm][aeons]{1,2}\b|\b[JjMm]\'')# + mien mienne
QUOTE=re.compile(r'["«»]')
BRACKET=re.compile(r'[(){}\[\]]')

PERSON=re.compile(r'Gender=[A-z]+\||Number=[A-z]+\||Person=*\|')

csv.field_size_limit(100000000)

def is_char(word):
    return not bool(NOT_CHAR.match(word))

def squeeze(txt): #pour être sur que le sent tokenizer de nltk marche bien
    txt=re.sub(r'[.]+', '.', txt)
    txt=re.sub(USELESS, ' ', txt)
    return txt

def clean(txt):
    txt=re.sub(HTML, ' ', txt)
    txt=re.sub(VIDE, ' ', txt)
    return txt


def generate_sources():

    f2=open('sources.csv', 'r')
    sources=csv.DictReader(f2)

    sources_list=set()

    for row in sources:
        source={'url': row['url'],
                'name':row['name'],
                'id':row['id'],
                'politics':row['politics'],
                'level0':row['level0_title'],
                'level1':row['level1_title'],
                'level2':row['level2_title'],
                'webentity':row['webentity']}
        sources_list.add(source)

    f2.close()

    return sources_list

def generate_stopwords():
    stopwords=set()
    with open ('stopwords_français.txt', 'r') as f:
        stopwords={word.strip() for word in f.readlines()}
    return stopwords

def generate_dictionary():
    dictionary=set()
    with open ('french.txt', 'r') as f:
        dictionary={word.strip() for word in f.readlines()}
    return dictionary


#def generate_linkingwords():



def calcul_verb(verbs, nb_verbs):
    result={}

    nb_past_verbs=0
    nb_fut_verbs=0
    nb_pres_verbs=0
    nb_imp_verbs=0
    nb_other_verbs=0

    tenses=defaultdict(set)
    persons=defaultdict(int)

    for verb in verbs:

        if 'Plur' in verb:
            persons['plur']+=1
        elif 'Sing' in verb:
            persons['sing']+=1

        tens=re.sub(PERSON, '', verb)
        if 'Pres' in tens:
            tenses['pres'].add(tens)
            nb_pres_verbs+=1
        elif 'Past' in tens:
            tenses['past'].add(tens)
            nb_past_verbs+=1
        elif 'Fut' in tens:
            tenses['fut'].add(tens)
            nb_fut_verbs+=1
        elif 'Imp' in tens:
            tenses['imp'].add(tens)
            nb_imp_verbs+=1
        else:
            tenses['others'].add(tens)
            nb_other_verbs+=1


    verbs_diversity=0
    for tens in tenses:
        verbs_diversity+=len(tens)


    result={}

    result['past_verb_cardinality']=(len(tenses['past'])/verbs_diversity)*100
    result['pres_verb_cardinality']=(len(tenses['pres'])/verbs_diversity)*100
    result['fut_verb_cardinality']=(len(tenses['fut'])/verbs_diversity)*100
    result['imp_verb_cardinality']=(len(tenses['imp'])/verbs_diversity)*100
    result['other_verb_cardinality']=(len(tenses['others'])/verbs_diversity)*100

    result['past_verb_prop']=(nb_past_verbs/nb_verbs)*100
    result['pres_verb_prop']=(nb_pres_verbs/nb_verbs)*100
    result['fut_verb_prop']=(nb_fut_verbs/nb_verbs)*100
    result['imp_verb_prop']=(nb_imp_verbs/nb_verbs)*100

    result['plur_verb_prop']=(persons['plur']/nb_verbs)*100
    result['sing_verb_prop']=(persons['sing']/nb_verbs)*100

    result['verbs_diversity']=(verbs_diversity/nb_verbs)*100

    return result

def calcul_punct(punctuations, nb_puncts):

    nb_sent=0
    nb_quote=0
    nb_bracket=0

    result={}

    for punct in punctuations.keys():
        if POINT.match(punct):
            nb_sent+=punctuations[punct]
        elif QUOTE.match(punct):
            nb_quote+=punctuations[punct]
        elif BRACKET.match(punct):
            nb_bracket+=punctuations[punct]

    if nb_quote%2!=0 or nb_bracket%2!=0:
        if nb_quote%2!=0:
            nb_quote+=1
        else:
            nb_bracket+=1
    else:
        nb_quote=nb_quote/2
        nb_bracket=nb_bracket/2

    result['question_prop']=(punctuations['?']/nb_sent)*100
    result['exclamative_prop']=(punctuations['!']/nb_sent)*100
    result['quote_prop']=(nb_quote/nb_sent)*100
    result['bracket_prop']=(nb_bracket/nb_sent)*100

    return result

def calcul_pos(pos_counting, nb_tokens):

    result={}

    result['noun_prop']=(pos_counting['NOUN']/nb_tokens)*100
    result['cconj_prop']=(pos_counting['CCONJ']/nb_tokens)*100
    result['adj_prop']=(pos_counting['ADJ']/nb_tokens)*100
    result['verb_prop']=((pos_counting['VERB']+pos_counting['AUX'])/nb_tokens)*100
    result['adv_prop']=(pos_counting['ADV']/nb_tokens)*100

    return result

#def calcul_ner(entities):

def pos_tagging(txt): #calcule certaines features en utilisant le pos tagging : temps (cardinalité temps), pos, punct, negation(marche pas top)

    txt=str(txt)
    with Timer('nlp'):
        txt = nlp(txt)

    pos_counting=defaultdict(int)
    negation=defaultdict(int)
    punctuations=defaultdict(int)
    verbs=[]
    entities=defaultdict(set)
    nb_word=0
    nb_char=0

    for token in txt:
        pos_counting[token.pos_]+=1

        if 'PUNCT' in token.pos_:
            punctuations[token.text]+=1
        elif 'VERB' in token.pos_ or 'AUX' in token.pos_:
           verbs.append(token.tag_)

    for ent in txt.ents:
        entities[ent.label_].add(ent.text)

    if verbs:
        nb_verbs=pos_counting['VERB']+pos_counting['AUX']
        verbs_results=calcul_verb(verbs, nb_verbs)
    else:
        verbs_results={}


    punctuation_results=calcul_punct(punctuations, pos_counting['PUNCT'])
    pos_results=calcul_pos(pos_counting,len(txt))
    #ner_results=calcul_ner(entities)
    results={}

    results.update(verbs_results)
    results.update(punctuation_results)
    results.update(pos_results)
    #results.update(ner_results)
    return results


## Pour les trucs avec re.match

def count_subjectivity(txt, nb_sent):
    subjectivities=re.findall(SUBJ, txt)
    return {'subjectivity_prop':(len(subjectivities)/nb_sent)*100}

def count_negation(txt, nb_sent): #mayday: la double négation
    negations=re.findall(NEGATION, txt)
    return {'prop_negation':(len(negations)/nb_sent)*100}

##Pour utiliser NLTK

def count_letters(letters, word):

    for char in word:
        if CHAR.match(char):
            letters[char]+=1

    return letters

def calcul_letters(letters, nb_char):

    nb_missing_letters=29-len(letters)
    for i in range(nb_missing_letters):
        letters[i]=0

    mean_occ_letter=0
    for nb_occ_letter in letters.values():
        mean_occ_letter+=nb_occ_letter


    mean_occ_letter=mean_occ_letter/29
    median_occ_letter=median(letters.values())

    return {
            'mean_occ_letter':mean_occ_letter,
            'median_occ_letter':median_occ_letter
            }


def calcul_ARI(txt, stopwords, dictionary): # on pourrait faire tout dans l'un à condition d'abandonner la médiane du nb de mots par phrase

    txt=squeeze(txt)
    sentences=nltk.tokenize.sent_tokenize(txt, language='french')
    txt=[nltk.word_tokenize(sentence) for sentence in sentences]

    ARI=0.0
    nb_word=0
    nb_char=0
    nb_sentence=0
    TYPE=''
    nb_shortwords=0
    nb_stopwords=0
    letters=defaultdict(int)
    voc=defaultdict(int)
    nb_dictwords=0

    nb_cw=[] # cw => char per word
    nb_ws=[] # ws => word per sent

    for sentence in txt:

        if len(sentence)>3 and len(sentence)<300:
            nb_sentence+=1

            for word in sentence:

                if is_char(word):

                    if len(word)<300:
                        word=word.lower()
                        voc[word]+=1
                        letters=count_letters(letters, word)
                        nb_word+=1
                        nb_char+=len(word)
                        nb_cw.append(len(word))

                    if len(word)<5:
                        nb_shortwords+=1
                    if word in stopwords:
                        nb_stopwords+=1
                    if word in dictionary:
                        nb_dictwords+=1

            nb_ws.append(len(sentence))


    mean_cw=nb_char/nb_word
    mean_ws=nb_word/nb_sentence

    median_cw=median(nb_cw)
    median_ws=median(nb_ws)


    prop_shortword=(nb_shortwords/nb_word)*100
    prop_dictwords=(nb_dictwords/nb_word)*100

    if nb_sentence>3:
        ARI=4.71*(mean_cw)+0.5*(mean_ws)-21.43


    if 0<ARI<30:
        result={
            'ARI':ARI ,
            'nb_sent':nb_sentence,
            'nb_word':nb_word,
            'nb_char':nb_char,
            'mean_cw':mean_cw,
            'mean_ws':mean_ws,
            'median_cw':median_cw,
            'median_ws':median_ws,
            'max_len_word':max(nb_cw),
            'prop_shortwords':prop_shortword,
            'prop_dictwords':prop_dictwords,
            'voc_cardinality':(len(voc)/nb_word)*100
            }
        result.update(calcul_letters(letters, nb_char))
        return result
    else:
        return False


def calcul_features(path):

    try:
        with open (path,'r') as ft:
            txt=ft.readline()
    except:
        return False

    results={}

    try:
        results.update(calcul_ARI(txt, stopwords, dictionary))

    except:
        return False

    results.update(pos_tagging(txt))
    results.update(count_negation(txt,results['nb_sent']))
    results.update(count_subjectivity(txt, results['nb_sent']))

    return results


##### Fonction pour calculer les nouvelles features sur tous les textes et les enregistrées

def generate_path(row):
    story_id=row['stories_id']
    return 'sample/'+story_id+'.txt'



def find_media_info(sources, media_id, info='level0'):

    for source in sources:
        if source['id']==media_id:
            return source

    return False

def produce_data():

    f_sample=open('sample_with_features.csv', 'r')
    samples=csv.DictReader(f_sample)

    sources=generate_sources()
    data={"values":[]}

    for row in samples:

        info=find_media_info(sources, row['media_id'])
        value={}

        if "" not in info:
            for key in row.keys():
                value[key]=row[key]
            for key in info.keys():
                value[key]=info[key]
            data['values'].append(value)

    f_sample.close()

    return data

def ajout_info():

    fs=open('sample_normalized_sorted.csv', 'r')
    reader=csv.DictReader(fs)
    reader.fieldnames+=['ARI', 'nb_sent', 'nb_word', 'nb_char', 'mean_cw', 'mean_ws', 'median_cw', 'median_ws', 'prop_shortwords', 'max_len_word', 'prop_dictwords', 'voc_cardinality', 'mean_occ_letter', 'median_occ_letter', 'prop_negation', 'subjectivity_prop', 'verb_prop', 'past_verb_cardinality', 'pres_verb_cardinality', 'fut_verb_cardinality', 'imp_verb_cardinality', 'other_verb_cardinality','past_verb_prop', 'pres_verb_prop', 'fut_verb_prop','imp_verb_prop', 'plur_verb_prop','sing_verb_prop','verbs_diversity','question_prop','exclamative_prop','quote_prop','bracket_prop','noun_prop','cconj_prop','adj_prop','adv_prop']

    fd=open('sample_with_features.csv', 'w')
    writer=csv.DictWriter(fd, fieldnames=reader.fieldnames)
    writer.writeheader()
    times=[]

    generator=((generate_path(row), row) for row in reader)
    print(generator)
    i=0
    for row in reader:
        i+=1
        story_id=row['stories_id']

        print('')
        print(story_id, i)

        with Pool(4) as pool:
            stopwords=generate_stopwords()
            dictionary=generate_dictionary()
            for features in pool.imap_unordered(calcul_features, generator):
                if features==False:
                    continue
                for key in features.keys():
                    row[key]=features[key]
                writer.writerow(row)

    fd.close()
    fs.close()

    return 0



#### Bonjor on travaille ####



ajout_info()