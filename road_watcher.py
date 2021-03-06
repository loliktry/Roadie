# -*- coding: utf-8 -*-
__author__ = 'quentinkaiser'
import twitter
import MySQLdb
from optparse import OptionParser
import time
import logging
import requests
from requests_oauthlib import OAuth1
import json
import sys
import configparser


class RoadWatcher:
    """

    """
    def __init__(self, config):
        """

        """
        self.config = config
        self.sleep_time = int(self.config['road_watcher']['update_time'])

        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self.logger = logging.getLogger("traffic")
        self.logger.setLevel(logging.INFO)

        default_file = logging.FileHandler(
            "%s-default.log" % str(self.config['road_watcher']['log_filename']),
            delay=True
        )
        default_file.setLevel(logging.INFO)
        default_file.setFormatter(formatter)
        self.logger.addHandler(default_file)
        default_file.close()

        error_file = logging.FileHandler(
            "%s-error.log" % str(self.config['road_watcher']['log_filename']),
            delay=True
        )
        error_file.setLevel(logging.ERROR)
        error_file.setFormatter(formatter)
        self.logger.addHandler(error_file)
        error_file.close()

        self.twitter_bots = {}
        try:
            for language in ['fr', 'nl', 'en', 'de']:
                self.twitter_bots[language] = twitter.Api(
                    consumer_key=self.config['twitter']['%s_consumer_key'%language],
                    consumer_secret=self.config['twitter']['%s_consumer_secret'%language],
                    access_token_key=self.config['twitter']['%s_access_token_key'%language],
                    access_token_secret=self.config['twitter']['%s_access_token_secret'%language]
                )

                if self.twitter_bots[language].VerifyCredentials() is None:
                    raise Exception("Twitter bot credentials are wroooong ! ")
        except Exception as e:
            self.logger.exception(e)
            sys.exit(0)
        self.last_fetch_time = int(time.time())

    def run(self):
        """

        """
        for language in ['fr', 'nl', 'en', 'de']:
            events = self.load_traffic(language)
            if len(events):
                self.notify_twitter(language, events)

        self.last_fetch_time = int(time.time())
        time.sleep(self.sleep_time)
        self.run()


    def notify_twitter(self, language, events):
        """

        """
        try:
            for event in events:
                share_url = "http://beroads.com/event/%s" % event['id']
                place_id = None

                auth = OAuth1(
                    self.config['twitter']['%s_consumer_key'%language],
                    self.config['twitter']['%s_consumer_secret'%language],
                    self.config['twitter']['%s_access_token_key'%language],
                    self.config['twitter']['%s_access_token_key'%language]
                )

                payload = {'lat': event['lat'], 'long': event['lng']}
                r = requests.get('https://api.twitter.com/1.1/geo/search.json', params=payload, auth=auth)

                if r.status_code == 200:
                    result = json.loads(r.content)
                    if len(result['result']['places']):
                        place_id = result['result']['places'][0]['id']

                status = "%s ... %s" % (
                    event['location'][0:(140 - len(share_url) - 4)], share_url)

                self.logger.info("Publishing status : %s on Twitter..." % status)

                self.twitter_bots[language].PostUpdate(status=status,
                    latitude=event['lat'],
                    longitude=event['lng'],
                    place_id=place_id,
                    display_coordinates=True
                )
        except Exception as e:
            self.logger.exception(e)


    def load_traffic(self, language):
        """

        """
        con = None
        cursor = None
        try:
            con = MySQLdb.connect(
                str(self.config['mysql']['host']),
                str(self.config['mysql']['username']),
                str(self.config['mysql']['password']),
                str(self.config['mysql']['database']),
                charset='utf8'
            )
            cursor = con.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute(
                "SELECT * FROM trafic WHERE language = '%s' AND insert_time > %d" % (language, self.last_fetch_time))

            return cursor.fetchall()
        except KeyboardInterrupt:
            if con:
                if cursor:
                    cursor.close()
                con.close()
            sys.exit(2)
        except MySQLdb.Error as e:
            self.logger.exception(e)
            if con:
                if cursor:
                    cursor.close()
                con.close()
            sys.exit(2)
        except Exception as e:
            self.logger.exception(e)
            if con:
                con.close()


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-c", "--config", type="string", default="config.ini", help="configuration file")
    (options, args) = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(options.config)

    while True:
    #this is a trick to be "error resilient", in fact the majority of errors that
    #we got is because our sources are not available or their server are too slow
    #by enabling this we don't stop the process on error and keep running ;-)
        try:
            road_watcher = RoadWatcher(config)
            road_watcher.run()
        except KeyboardInterrupt as e:
            logging.exception(e)
            sys.exit(0)
        except Exception as e:
            logging.exception(e)
            continue
        break
