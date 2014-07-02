Instance timeout helper
================================

This App Engine application monitors your Google Compute Engine instances and deletes any non-production instances once they're 8 hours old. This helps avoid accidentally running instances for a long time. Any instances tagged "production" will be left running.

> WARNING: When instances are stopped, all data on ephemeral disks is destroyed. This application looks at ALL instances in a project and will delete any instances which aren't tagged "production". For extra safety, the application defaults to running in DRY_RUN mode, where deletes are logged, but not applied. 

This sample application demonstrates:

 * Using the [Compute Engine API](https://developers.google.com/compute/docs/reference/latest/) from App Engine, specifically: listing instances and deleting instances. The same pattern can be used for other GCE API calls.
 * [App identity based API authorization](https://developers.google.com/appengine/docs/python/appidentity/overview) from AppEngine - no shared secrets, no passwords, minimal configuration.

You can configure how often the application checks the instances, which tags will be left alone and how long instances are allowed to run before deleting them.


Prerequisites
-------------

1. A Google API project with the Google Compute Engine API enabled.
2. Admin rights on an App Engine application.
3. The App Engine Python SDK installed on your computer.


Setup
-----

Clone the git repository for this project to your computer:

    $ git clone REPOSITORY-URL

Install [Google API Python Client with dependencies for App Engine](http://code.google.com/p/google-api-python-client/downloads/list).
Visit the download page, find "Full Dependecies Build for Google App Engine Projects" and download it into the root of your repository, for example:

    $ wget http://google-api-python-client.googlecode.com/files/google-api-python-client-gae-1.0.zip

Unzip it into the root of your repository:

    $ unzip google-api-python-client-gae-1.0.zip


Configuration
-------------

You will need to make three configuration changes before deploying.

`app.yaml`: Change the value of `application:` to your App Engine application ID.

`main.py`: Change the value of `GCE_PROJECT_ID` to your project id which has GCE enabled.

Give your App Engine application's service account `edit` access to your GCE project.

 * Log into the App Engine Admin Console.
 * Click on the application you want to authorize.
 * Click on Application Settings under the Administration section on the left-hand side.
 * Copy the value under Service Account Name. This is the service account name of your application, in the format application-id@appspot.gserviceaccount.com. If you are using an App Engine Premier Account, the service account name for your application is in the format application-id.example.com@appspot.gserviceaccount.com.
 * Use the Google APIs Console to add the service account name of the app as a team member to the project. Give the account `edit` permission.


Verify
------

> As long as DRY_RUN is set to `True` (the default) in `main.py`, the application will only log deletes.

Deploy the application to App Engine:

    $ appcfg.py update .

> Note: Because this application is using GAE app identity for authentication to GCE, it will not work on the local development server.

View the index at the root of the application, at `http://YOUR-APP-ID.appspot.com`.
Check that production instances are being excluded and older instances would be deleted. 

To create instances tagged "production", add the instance using the GCE Console and include "production" in the tags field. Or add it using gcutil:

    $ gcutil addinstance instance-name --tags=production,another-tag

You can optionally run the cron task manually and check the logs to verify that the correct instances will be deleted. 

Visit `http://YOUR-APP-ID.appspot.com/cron/delete` to run deletes immediately. Then check the AppEngine logs. You should see "DRY_RUN, not deleted" if any instances are old enough to be deleted.

Once everything looks good, edit `main.py` and change `DRY_RUN` to `False`.

Happy Computing!
