import datetime
import logging
import os

import flask
import jinja2
import requests
import werkzeug

import bhamon_orchestra_website
import bhamon_orchestra_website.helpers as helpers
import bhamon_orchestra_website.service_client as service_client

import bhamon_orchestra_website.admin_controller as admin_controller
import bhamon_orchestra_website.job_controller as job_controller
import bhamon_orchestra_website.me_controller as me_controller
import bhamon_orchestra_website.project_controller as project_controller
import bhamon_orchestra_website.run_controller as run_controller
import bhamon_orchestra_website.schedule_controller as schedule_controller
import bhamon_orchestra_website.user_controller as user_controller
import bhamon_orchestra_website.worker_controller as worker_controller


main_logger = logging.getLogger("Website")
request_logger = logging.getLogger("Request")


def configure(application, title = None, copyright = None, version = None, date = None): # pylint: disable = redefined-builtin
	application.config["WEBSITE_TITLE"] = title if title is not None else "Job Orchestra"
	application.config["WEBSITE_COPYRIGHT"] = copyright if copyright is not None else bhamon_orchestra_website.__copyright__
	application.config["WEBSITE_VERSION"] = version if version is not None else bhamon_orchestra_website.__version__
	application.config["WEBSITE_DATE"] = date if date is not None else bhamon_orchestra_website.__date__

	application.jinja_env.undefined = jinja2.StrictUndefined()
	application.jinja_env.trim_blocks = True
	application.jinja_env.lstrip_blocks = True
	application.jinja_env.filters["describe_cron_expression"] = helpers.describe_cron_expression
	application.jinja_env.globals["authorize_view"] = authorize_view
	application.permanent_session_lifetime = datetime.timedelta(days = 7)
	application.session_refresh_interval = datetime.timedelta(days = 1)


def register_handlers(application):
	application.log_exception = lambda exc_info: None
	application.before_request(log_request)
	application.before_request(refresh_session)
	application.before_request(authorize_request)
	for exception in werkzeug.exceptions.default_exceptions:
		application.register_error_handler(exception, handle_error)


def register_routes(application):
	add_url_rule(application, "/", [ "GET" ], home)
	add_url_rule(application, "/admin", [ "GET" ], admin_controller.index)
	add_url_rule(application, "/me", [ "GET" ], me_controller.show_profile)
	add_url_rule(application, "/me/login", [ "GET", "POST" ], me_controller.login)
	add_url_rule(application, "/me/logout", [ "GET", "POST" ], me_controller.logout)
	add_url_rule(application, "/me/refresh_session", [ "POST" ], me_controller.refresh_session)
	add_url_rule(application, "/me/change_password", [ "GET", "POST" ], me_controller.change_password)
	add_url_rule(application, "/me/token_create", [ "GET", "POST" ], me_controller.create_token)
	add_url_rule(application, "/me/token/<token_identifier>/delete", [ "POST" ], me_controller.delete_token)
	add_url_rule(application, "/project_collection", [ "GET" ], project_controller.show_collection)
	add_url_rule(application, "/project/<project_identifier>", [ "GET" ], project_controller.show)
	add_url_rule(application, "/project/<project_identifier>/status", [ "GET" ], project_controller.show_status)
	add_url_rule(application, "/project/<project_identifier>/job_collection", [ "GET" ], job_controller.show_collection)
	add_url_rule(application, "/project/<project_identifier>/job/<job_identifier>", [ "GET" ], job_controller.show)
	add_url_rule(application, "/project/<project_identifier>/job/<job_identifier>/trigger", [ "POST" ], job_controller.trigger)
	add_url_rule(application, "/project/<project_identifier>/job/<job_identifier>/enable", [ "POST" ], job_controller.enable)
	add_url_rule(application, "/project/<project_identifier>/job/<job_identifier>/disable", [ "POST" ], job_controller.disable)
	add_url_rule(application, "/project/<project_identifier>/run_collection", [ "GET" ], run_controller.show_collection)
	add_url_rule(application, "/project/<project_identifier>/run/<run_identifier>", [ "GET" ], run_controller.show)
	add_url_rule(application, "/project/<project_identifier>/run/<run_identifier>/step/<int:step_index>", [ "GET" ], run_controller.show_step)
	add_url_rule(application, "/project/<project_identifier>/run/<run_identifier>/step/<int:step_index>/log", [ "GET" ], run_controller.show_step_log)
	add_url_rule(application, "/project/<project_identifier>/run/<run_identifier>/cancel", [ "POST" ], run_controller.cancel)
	add_url_rule(application, "/project/<project_identifier>/run/<run_identifier>/abort", [ "POST" ], run_controller.abort)
	add_url_rule(application, "/project/<project_identifier>/run/<run_identifier>/download", [ "GET" ], run_controller.download_archive)
	add_url_rule(application, "/project/<project_identifier>/schedule_collection", [ "GET" ], schedule_controller.show_collection)
	add_url_rule(application, "/project/<project_identifier>/schedule/<schedule_identifier>", [ "GET" ], schedule_controller.show)
	add_url_rule(application, "/project/<project_identifier>/schedule/<schedule_identifier>/enable", [ "POST" ], schedule_controller.enable)
	add_url_rule(application, "/project/<project_identifier>/schedule/<schedule_identifier>/disable", [ "POST" ], schedule_controller.disable)
	add_url_rule(application, "/user_collection", [ "GET" ], user_controller.show_collection)
	add_url_rule(application, "/user_create", [ "GET", "POST" ], user_controller.create)
	add_url_rule(application, "/user/<user_identifier>", [ "GET" ], user_controller.show)
	add_url_rule(application, "/user/<user_identifier>/edit", [ "GET" ], user_controller.edit)
	add_url_rule(application, "/user/<user_identifier>/update_identity", [ "POST" ], user_controller.update_identity)
	add_url_rule(application, "/user/<user_identifier>/update_roles", [ "POST" ], user_controller.update_roles)
	add_url_rule(application, "/user/<user_identifier>/enable", [ "POST" ], user_controller.enable)
	add_url_rule(application, "/user/<user_identifier>/disable", [ "POST" ], user_controller.disable)
	add_url_rule(application, "/user/<user_identifier>/reset_password", [ "GET", "POST" ], user_controller.reset_password)
	add_url_rule(application, "/user/<user_identifier>/token_create", [ "GET", "POST" ], user_controller.create_token)
	add_url_rule(application, "/user/<user_identifier>/token/<token_identifier>/delete", [ "POST" ], user_controller.delete_token)
	add_url_rule(application, "/worker_collection", [ "GET" ], worker_controller.show_collection)
	add_url_rule(application, "/worker/<worker_identifier>", [ "GET" ], worker_controller.show)
	add_url_rule(application, "/worker/<worker_identifier>/runs", [ "GET" ], worker_controller.show_runs)
	add_url_rule(application, "/worker/<worker_identifier>/disconnect", [ "POST" ], worker_controller.disconnect)
	add_url_rule(application, "/worker/<worker_identifier>/enable", [ "POST" ], worker_controller.enable)
	add_url_rule(application, "/worker/<worker_identifier>/disable", [ "POST" ], worker_controller.disable)
	add_url_rule(application, "/service_proxy", [ "GET", "POST" ], proxy_to_service, defaults = { "route": "" })
	add_url_rule(application, "/service_proxy/<path:route>", [ "GET", "POST" ], proxy_to_service)


def add_url_rule(application, path, methods, handler, **kwargs):
	endpoint = ".".join(handler.__module__.split(".")[1:]) + "." + handler.__name__
	application.add_url_rule(path, methods = methods, endpoint = endpoint, view_func = handler, **kwargs)


def register_resources(application, path_collection = None):
	if application.static_folder is not None:
		raise ValueError("Flask application should be initialized with static_folder set to None")

	if path_collection is None:
		path_collection = [ os.path.dirname(__file__) ]

	application.static_directories = [ os.path.join(path, "static") for path in path_collection ]
	application.add_url_rule("/static/<path:filename>", view_func = send_static_file, endpoint = "static")
	application.jinja_loader = jinja2.ChoiceLoader([ jinja2.FileSystemLoader(os.path.join(path, "templates")) for path in path_collection ])


def log_request():
	request_logger.info("(%s) %s %s", flask.request.environ["REMOTE_ADDR"], flask.request.method, flask.request.base_url)


def refresh_session():
	if "token" in flask.session:
		now = flask.current_app.date_time_provider.now()
		last_refresh = flask.session.get("last_refresh", None)

		if last_refresh is None or now > (last_refresh + flask.current_app.session_refresh_interval):
			try:
				service_client.post("/me/refresh_session", { "token_identifier": flask.session["token"]["token_identifier"] })
				flask.session["user"] = service_client.get("/me")
				flask.session["last_refresh"] = now
			except requests.HTTPError as exception:
				if exception.response.status_code == 403:
					flask.session.clear()

	flask.request.user = flask.session.get("user", None)


def authorize_request():
	if flask.request.url_rule is None:
		return
	if not flask.current_app.authorization_provider.authorize_request(flask.request.user, flask.request.method, flask.request.url_rule.rule):
		flask.abort(403)


def authorize_view(view):
	return flask.current_app.authorization_provider.authorize_view(flask.request.user, view)


def handle_error(exception):
	status_code = exception.code if isinstance(exception, werkzeug.exceptions.HTTPException) else 500
	status_message = helpers.get_error_message(status_code)
	request_logger.error("(%s) %s %s (StatusCode: %s)", flask.request.environ["REMOTE_ADDR"], flask.request.method, flask.request.base_url, status_code, exc_info = True)
	if flask.request.headers.get("Content-Type") == "application/json":
		return flask.jsonify({ "status_code": status_code, "status_message": status_message }), status_code
	return flask.render_template("error.html", title = "Error", status_message = status_message, status_code = status_code), status_code


# Override Flask send_static_file to support several static directories
def send_static_file(filename):
	if not flask.current_app.static_directories:
		raise RuntimeError('Flask application has no static directory')

	# Ensure get_send_file_max_age is called in all cases.
	# Here, we ensure get_send_file_max_age is called for Blueprints.
	cache_timeout = flask.current_app.get_send_file_max_age(filename)

	for directory in flask.current_app.static_directories:
		try:
			return flask.helpers.send_from_directory(directory, filename, cache_timeout = cache_timeout)
		except werkzeug.exceptions.NotFound:
			pass

	raise werkzeug.exceptions.NotFound


def home():
	return flask.render_template("home.html", title = "Home")


def proxy_to_service(route):
	service_response = service_client.proxy("/" + route)

	response = flask.Response(service_response.content, service_response.status_code)
	for header_key in service_response.headers:
		if header_key in [ "Content-Type" ] or header_key.startswith("X-Orchestra-"):
			response.headers[header_key] = service_response.headers[header_key]

	return response
