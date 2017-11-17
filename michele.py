# -*- coding: utf-8 -*-
#17nov17
from bs4 import BeautifulSoup
import feedparser
import telegram
from telegram.error import *
import urllib.request
from telegram.ext import *
from urllib.request import urlopen 
import postgresql
import feedparser
from html_to_telegraph import *
from errors import *
import os

TOKEN_TELEGRAM = os.environ['TOKEN_TELEGRAM'] 
bot = telegram.Bot(TOKEN_TELEGRAM)
STRING_DB = os.environ['DATABASE_URL'].replace("postgres","pq")
CHAT_ID_LIST = os.environ['CHAT_ID_LIST'].split(",")
feed = 'http://home.cern/about/updates/newsletter_feed'
url = 'http://home.cern/about/updates/2017/11/how-much-does-kilogram-weigh'

def init_DB():
	global STRING_DB
	db = postgresql.open(STRING_DB)
	ps = db.prepare("CREATE TABLE IF NOT EXISTS url (id serial PRIMARY KEY, url varchar(300) unique);")
	ps()          
db.close()

def getArticles( bot, job ):
	global STRING_DB
	db = postgresql.open(STRING_DB)
	ps = db.prepare("SELECT * FROM url;")
	allUrl = [ item[1] for item in ps() ]
	entries = feedparser.parse( feed ).entries
	for post in reversed(entries):
		if post.link not in allUrl:
			try:
				ps = db.prepare("INSERT INTO url (url) VALUES ('{}') ON CONFLICT (url) DO NOTHING;".format(post.link) )
				ps()
				html = urlopen(url).read()
				bsObj = BeautifulSoup(html,"html.parser")
				title = bsObj.findAll("title")[0].text.strip().replace(" | CERN","")
				body = bsObj.findAll("div", {"class":"field-body"})[0]
				mainImage = bsObj.findAll("div", {"class":"field-image"})[0].a["href"]
				author = bsObj.findAll("p",{"class":"field-byline-taxonomy"})[0].text

				# PROBLEMA se la src di un immagine non e' completa tipo 
				# <img alt="" src="/sites/home.web.cern.ch/files/image/inline-images/cmenard/luminosity-lhc-2017.jpg"
				# invece di essere
				# <img alt="" src="http://home.cern/sites/home.web.cern.ch/files/image/inline-images/cmenard/luminosity-lhc-2017.jpg"
				# telegraph non riesce a mandare l'instant view
				# e l'immagine neanche non si carica
				# con codice seguente aggiungo la stringa http://home.cern/ alle immagini
				i = 0
				bsObjIMG = body.findAll("img")
				listIMG = [ i['src'] for i in bsObjIMG ]

				body = str( body )
				for IMG in listIMG:
					baseUrl  = 'http://home.cern/'
					if baseUrl not in IMG: 
						STR = '<a href="{}"> <img src="http://home.cern{}" />  </a>'.format(IMG,IMG)
						body = body.replace( str(bsObjIMG[i]), STR )
					i = i+1
				print(mainImage)
				body = body.replace("<div>","")
				body = body.replace("</div>","")

				body = '<img src="{}" />'.format(mainImage, mainImage) + body.rstrip()

				url2send = upload_to_telegraph(title=title, author=author, text=body)["url"]
				text2send = '<b>{}</b>\n<a href="{}">[LINK]</a>/<a href="{}">[ORIGINAL]</a>'.format(title,url2send, url)
				for chat_id in CHAT_ID_LIST:
					try:
						bot.sendMessage(parse_mode = "Html", text = text2send, chat_id = int(chat_id) )
						sleep(3)
					except Exception as e:
						#messaggio non inviato...perche' l'utente ha bloccato il bot???
						print("Error sending msg to chat_id {}".format(chat_id) )
						print(e)
						continue
			except Exception as e:
				print(e)

def start( bot, update ):
	bot.sendMessage(chat_id = update.message.chat_id, text = "Successfully subscribed.")

init_DB()
updater = Updater(TOKEN_TELEGRAM) 
dp = updater.dispatcher
updater.dispatcher.add_handler(CommandHandler('start', start))
j = updater.job_queue
j.run_repeating(getArticles, 3600)
updater.start_polling()
updater.idle()
