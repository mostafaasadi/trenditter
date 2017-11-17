from __future__ import unicode_literals
from os import path
from PIL import Image
import numpy as np
import datetime
import pymongo
from mongoHandler import MongoHandler
from config import *
from persian_wordcloud.wordcloud import STOPWORDS, PersianWordCloud
import arabic_reshaper
from bidi.algorithm import get_display
from hazm import *
from utils import *

d = path.dirname(__file__)

tagger = POSTagger(model=path.join(d, 'resources/postagger.model'))
normalizer = Normalizer()
stemmer = Stemmer()
lemmatizer = Lemmatizer()
# chunker = Chunker(model=path.join(d, 'resources/chunker.model'))


TypeBlacklist = [
    'CONJ',
    'PUNC',
    'ADJP'
]

# convert rtl words like Arabic and Farsi to some showable form
def convert(text):
    new_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(new_text)
    return bidi_text

def is_perisan(s):
        return u'\u0600' <= s <= u'\u06FF'


# generating stopwords
STOPWORDS.add('می')
STOPWORDS.add('ای')
STOPWORDS.add('یه')
STOPWORDS.add('سر')
STOPWORDS.add('کن')
STOPWORDS.add('رو')
STOPWORDS.add('من')
STOPWORDS.add('تر')
STOPWORDS.add('اگه')
STOPWORDS.add('کنم')
STOPWORDS.add('کنه')
STOPWORDS.add('پر')
STOPWORDS.add('لا')
STOPWORDS.add('فی')
STOPWORDS.add('چی')
STOPWORDS.add('تو')
STOPWORDS.add('فک')
STOPWORDS.add('الان')
STOPWORDS.add('اون')
STOPWORDS.add('کردن')
STOPWORDS.add('نمی')
STOPWORDS.add('های')
STOPWORDS.add('باید')
STOPWORDS.add('دیگه')
stopwords = set(STOPWORDS)
stopwords_list = open(path.join(d, 'blacklist.txt')).read()
for word in stopwords_list.split():
    stopwords.add(convert(word))
    stopwords.add(word)

mongo = MongoHandler(mongo_connString, mongo_db, mongo_collection)
LastTweetToCheck = datetime.datetime.utcnow() - datetime.timedelta(seconds=wordCloudTimeout)
findQuery = {"retweeted_status.created_at": {'$gte': LastTweetToCheck}}
finderCursor = mongo._collection.find(findQuery)
print(finderCursor.count())
tweet_cnt = finderCursor.count()

all_words = []
checked = {}
# Read the whole text.
for tweet in finderCursor:
    if 'retweeted_status' in tweet:
        tweet_id = tweet['retweeted_status']['id_str']
        txt = tweet['retweeted_status']['text']
        if tweet['retweeted_status']['id_str'] not in checked:
            checked[tweet_id] = 0
        else:
            continue
    else:
        tweet_id = tweet['id_str']
        txt = tweet['text']
        if tweet['id_str'] not in checked:
            checked[tweet_id] = 0
        else:
            continue

    checked[tweet_id] += 1
    txt = re.sub("(@[A-Za-z0-9_]+)|(?:\@|https?\://)\S+", " ", txt)
    txt = normalizer.normalize(txt)
    for sentence in sent_tokenize(txt):
        tagged_txt = tagger.tag(word_tokenize(sentence))
        for word in tagged_txt:
            if word[1] not in TypeBlacklist:
                if word[0] not in stopwords:
                    try:
                        convert(' ' + word[0])
                        new_stemmed_word = stemmer.stem(word[0])
                        new_lemmatized_word = lemmatizer.lemmatize(word[0], pos=word[1])
                        if word[1] == 'V':
                            new_lemmatized_word = new_lemmatized_word.split('#')[0]
                        all_words.append(normalize(new_lemmatized_word))
                    except:
                        print("e")

text = '\n'.join(all_words)
print("finished")

# loading the mask
twitter_mask = np.array(Image.open(path.join(d, "twitter_mask.png")))

# generating wordcloud
wc = PersianWordCloud(only_persian=True, regexp=r".*\w+.*", font_step=3, font_path=path.join(d, "IRANSans.ttf"),
            background_color="white", max_words=800, mask=twitter_mask, stopwords=stopwords)
wc.generate(text)


currTime = datetime.datetime.utcnow()
output_name = currTime.strftime("%d-%m-%Y_%H_%M.png")

# store to file
wc.to_file(path.join(d, output_name))


import tweepy
import telegram
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)
telegram_bot = telegram.Bot(token=telegram_bot_token)

api.update_with_media(path.join(d, output_name), u'توییتر به روایت تصویر پس از پردازش ' + str(tweet_cnt) + u' توییت!')
wctg = telegram_bot.send_photo(chat_id="@trenditter", photo=open(path.join(d, output_name), 'rb'), caption=u'توییتر به روایت تصویر پس از پردازش ' + str(tweet_cnt) + u' توییت!')

telegram_bot.forwardMessage(chat_id="322219318", from_chat_id="@trenditter", message_id=wctg.message_id)

# telegram_bot.send_photo(chat_id=admin_id, photo=open(path.join(d, output_name), 'rb'), caption=u'توییتر به روایت تصویر پس از پردازش ' + str(tweet_cnt) + u' توییت!')
