import flask
import requests


def proxy(route):
	method = flask.request.method
	url = flask.current_app.service_url + route

	headers = {}
	for header_key, header_value in flask.request.headers:
		if header_key in [ "Accept", "Content-Type" ] or header_key.startswith("X-Orchestra-"):
			headers[header_key] = header_value

	parameters = flask.request.args
	data = flask.request.get_data()
	authentication = _get_authentication()

	return requests.request(method, url, auth = authentication, headers = headers, params = parameters, data = data)


def get_or_default(route, parameters = None, default_value = None):
	try:
		result = get(route, parameters = parameters)
		if result is not None:
			return result
	except requests.HTTPError as exception:
		if exception.response.status_code != "404":
			raise
	return default_value


def get(route, parameters = None):
	return send_request("GET", route, headers = { "Accept": "application/json" }, parameters = parameters).json()


def post(route, data = None):
	return send_request("POST", route, headers = { "Accept": "application/json" }, data = data).json()


def send_request(method, route, headers = None, parameters = None, data = None):
	authentication = _get_authentication()

	if headers is None:
		headers = {}

	if data is not None:
		headers["Content-Type"] = "application/json"
		# data = "FIXME" # FIXME


	response = requests.request(method, flask.current_app.service_url + route, auth = authentication, headers = headers, params = parameters, data = data)
	response.raise_for_status()
	return response


def _get_authentication():
	if "token" not in flask.session:
		return None
	return flask.session["token"]["user_identifier"], flask.session["token"]["secret"]
