#!/usr/bin/env python
#
# Copyright 2012 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import httplib2
import json
import logging
from pprint import pformat

import jinja2
import webapp2
from apiclient.discovery import build
from google.appengine.api import memcache
from oauth2client.appengine import AppAssertionCredentials

SAMPLE_NAME = 'Instance timeout helper'

CONFIG = {
    # In DRY_RUN mode, deletes are only logged. Set this to False after you've
    # double-checked the status page and you're ready to enable the deletes.
    'DRY_RUN': True,

    # Be careful, this application could delete all instances in this project.
    # Your project id can be found on the overview tab of the Google APIs
    # Console: https://code.google.com/apis/console/
    'GCE_PROJECT_ID': 'replace-with-your-compute-engine-project-id',

    # Instances created with these tags will never be deleted.
    'SAFE_TAGS': ['production', 'safetag'],

    # Instances are deleted after they have been running for TIMEOUT minutes.
    'TIMEOUT': 60 * 8,  # in minutes, defaulting to 8 hours
}
CONFIG['SAFE_TAGS'] = [t.lower() for t in CONFIG['SAFE_TAGS']]

# Obtain App Engine AppAssertion credentials and authorize HTTP connection.
# https://developers.google.com/appengine/docs/python/appidentity/overview
credentials = AppAssertionCredentials(
    scope='https://www.googleapis.com/auth/compute')
HTTP = credentials.authorize(httplib2.Http(memcache))

# Build object for the 'v1beta13' version of the GCE API.
# https://developers.google.com/compute/docs/reference/v1beta13/
compute = build('compute', 'v1beta15', http=HTTP)
jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'))


def annotate_instances(instances):
    """loops through the instances and adds exclusion, age and timeout"""
    for inst in instances:
        # set _excluded
        excluded = False
        tags = inst.get('tags', {}).get('items', [])
        inst['_tags'] = tags

        for tag in tags:
            if tag.lower() in CONFIG['SAFE_TAGS']:
                excluded = True
                break
        inst['_excluded'] = excluded

        # set _age_minutes and _timeout_expired
        # _timeout_expired is never True for _excluded inst
        creation = parse_iso8601tz(inst['creationTimestamp'])
        now = datetime.datetime.now()
        delta = now - creation
        age_minutes = (delta.days * 24 * 60) + (delta.seconds / 60)
        inst['_age_minutes'] = age_minutes
        # >= comparison because seconds are truncated above.
        if not inst['_excluded'] and age_minutes >= CONFIG['TIMEOUT']:
            inst['_timeout_expired'] = True
        else:
            inst['_timeout_expired'] = False


def list_instances():
    """returns a list of dictionaries containing GCE instance data"""
    request = compute.instances().aggregatedList(project=CONFIG['GCE_PROJECT_ID'])
    response = request.execute()
    zones = response.get('items', {})
    instances = []
    for zone in zones.values():
        for instance in zone.get('instances', []):
            instances.append(instance)
    annotate_instances(instances)
    return instances


class MainHandler(webapp2.RequestHandler):
    """index handler, displays app configuration and instance data"""
    def get(self):
        instances = list_instances()

        data = {}
        data['config'] = CONFIG
        data['title'] = SAMPLE_NAME
        data['instances'] = instances
        data['raw_instances'] = json.dumps(instances, indent=4, sort_keys=True)

        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render(data))


def delete_expired_instances():
    """logs all expired instances, calls delete API when not DRY_RUN"""
    instances = list_instances()

    # filter instances, keep only expired instances
    instances = [i for i in instances if i['_timeout_expired']]

    logging.info('delete cron: %s instance%s to delete',
                 len(instances), '' if len(instances) == 1 else 's')

    for instance in instances:
        name = instance['name']
        zone = instance['zone'].split('/')[-1]
        if CONFIG['DRY_RUN']:
            logging.info("DRY_RUN, not deleted: %s", name)
        else:
            logging.info("DELETE: %s", name)
            request = compute.instances().delete(
                                    project=CONFIG['GCE_PROJECT_ID'],
                                    instance=name,
                                    zone=zone)
            response = request.execute()
            logging.info(response)


class DeleteHandler(webapp2.RequestHandler):
    """delete handler - HTTP endpoint for the GAE cron job"""
    def get(self):
        delete_expired_instances()


app = webapp2.WSGIApplication([
    ('/cron/delete', DeleteHandler),
    ('/', MainHandler),
], debug=True)


# ------------------------------------------------
# helpers
def parse_iso8601tz(date_string):
    """return a datetime object for a string in ISO 8601 format.

    This function parses strings in exactly this format:
    '2012-12-26T13:31:47.823-08:00'

    Sadly, datetime.strptime's %z format is unavailable on many platforms,
    so we can't use a single strptime() call.
    """

    dt = datetime.datetime.strptime(date_string[:-6],
                                    '%Y-%m-%dT%H:%M:%S.%f')

    # parse the timezone offset separately
    delta = datetime.timedelta(minutes=int(date_string[-2:]),
                               hours=int(date_string[-5:-3]))
    if date_string[-6] == '-':
        # add the delta to return to UTC time
        dt = dt + delta
    else:
        dt = dt - delta
    return dt
