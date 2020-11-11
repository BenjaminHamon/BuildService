import logging

import flask
import requests

import bhamon_orchestra_website.helpers as helpers
import bhamon_orchestra_website.service_client as service_client


logger = logging.getLogger("UserController")


def show_collection():
	item_total = service_client.get("/user_count")
	pagination = helpers.get_pagination(item_total, {})

	query_parameters = {
		"skip": (pagination["page_number"] - 1) * pagination["item_count"],
		"limit": pagination["item_count"],
		"order_by": [ "identifier ascending" ],
	}

	view_data = {
		"user_collection": service_client.get("/user_collection", query_parameters),
		"pagination": pagination,
	}

	return flask.render_template("user/collection.html", title = "Users", **view_data)


def show(user_identifier): # pylint: disable = unused-argument
	user = service_client.get("/user/{user_identifier}".format(**locals()))

	view_data = {
		"user": user,
	}

	if flask.current_app.authorization_provider.authorize_view(flask.request.user, "user-security"):
		user_tokens = service_client.get("/user/{user_identifier}/token_collection".format(**locals()), { "order_by": [ "update_date descending" ] })
		user_tokens.sort(key = lambda token: token["expiration_date"] is not None)

		now = flask.current_app.date_time_provider.now()
		for token in user_tokens:
			token["is_active"] = token["expiration_date"] > now if token["expiration_date"] is not None else True

		view_data["user_tokens"] = user_tokens

	return flask.render_template("user/index.html", title = "User " + user["display_name"], **view_data)


def create():
	if flask.request.method == "GET":
		return flask.render_template("user/create.html", title = "Create User")

	if flask.request.method == "POST":
		user_identifier = flask.request.form["identifier"]
		parameters = { "display_name": flask.request.form["display_name"] }

		try:
			service_client.post("/user/{user_identifier}/create".format(**locals()), data = parameters)
			flask.flash("User '%s' was created successfully." % user_identifier, "success")
			return flask.redirect(flask.url_for("user_controller.show_collection"))
		except requests.HTTPError as exception:
			flask.flash("User '%s' could not be created: %s." % (user_identifier, helpers.get_error_message(exception.response.status_code)), "error")
			return flask.render_template("user/create.html", title = "Create User")

	return flask.abort(405)


def edit(user_identifier, local_parameters = None): # pylint: disable = unused-argument
	if local_parameters is None:
		local_parameters = {}

	user = service_client.get("/user/{user_identifier}".format(**locals()))

	flask.request.form = user
	flask.request.form.update(local_parameters)
	flask.request.form["roles"] = "\n".join(flask.request.form["roles"])
	return flask.render_template("user/edit.html", title = "Edit User", user = user)


def update_identity(user_identifier):
	parameters = { "display_name": flask.request.form["display_name"] }

	try:
		service_client.post("/user/{user_identifier}/update_identity".format(**locals()), data = parameters)
		flask.flash("Identity for user '%s' was updated successfully." % user_identifier, "success")
	except requests.HTTPError as exception:
		flask.flash("Identity for user '%s' could not be updated: %s." % (user_identifier, helpers.get_error_message(exception.response.status_code)), "error")
	return edit(user_identifier, parameters)


def update_roles(user_identifier):
	parameters = { "roles": [ role.strip() for role in flask.request.form["roles"].splitlines() ] }

	try:
		service_client.post("/user/{user_identifier}/update_roles".format(**locals()), data = parameters)
		flask.flash("Roles for user '%s' were updated successfully." % user_identifier, "success")
	except requests.HTTPError as exception:
		flask.flash( "Roles for user '%s' could not be updated: %s." % (user_identifier, helpers.get_error_message(exception.response.status_code)), "error")
	return edit(user_identifier, parameters)


def enable(user_identifier): # pylint: disable = unused-argument
	service_client.post("/user/{user_identifier}/enable".format(**locals()))
	return flask.redirect(flask.request.referrer or flask.url_for("user_controller.show_collection"))


def disable(user_identifier): # pylint: disable = unused-argument
	service_client.post("/user/{user_identifier}/disable".format(**locals()))
	return flask.redirect(flask.request.referrer or flask.url_for("user_controller.show_collection"))


def reset_password(user_identifier):
	if flask.request.method == "GET":
		user = service_client.get("/user/{user_identifier}".format(**locals()))
		return flask.render_template("user/reset_password.html", title = "Reset User Password", user = user)

	if flask.request.method == "POST":
		parameters = { "password": flask.request.form["password"] }

		try:
			service_client.post("/user/{user_identifier}/reset_password".format(**locals()), data = parameters)
			flask.flash("Password for user '%s' was set successfully." % user_identifier, "success")
			return flask.redirect(flask.url_for("user_controller.show", user_identifier = user_identifier))
		except requests.HTTPError as exception:
			flask.flash("Password for user '%s' could not be set: %s." % (user_identifier, helpers.get_error_message(exception.response.status_code)), "error")
			user = service_client.get("/user/{user_identifier}".format(**locals()))
			return flask.render_template("user/reset_password.html", title = "Reset User Password", user = user)

	return flask.abort(405)


def create_token(user_identifier):
	if flask.request.method == "GET":
		user = service_client.get("/user/{user_identifier}".format(**locals()))
		return flask.render_template("user/create_token.html", title = "Create User Authentication Token", user = user)

	if flask.request.method == "POST":
		parameters = { "description": flask.request.form["description"] }
		if flask.request.form["expiration"]:
			parameters["expiration"]  = flask.request.form["expiration"]

		try:
			token = service_client.post("/user/{user_identifier}/token_create".format(**locals()), data = parameters)
			flask.flash("Token '%s' was created successfully." % token["token_identifier"], "success")
			flask.flash("Token secret: '%s'." % token["secret"], "info")
			return flask.redirect(flask.url_for("user_controller.show", user_identifier = user_identifier))
		except requests.HTTPError as exception:
			flask.flash("Token could not be created: %s." % helpers.get_error_message(exception.response.status_code), "error")
			user = service_client.get("/user/{user_identifier}".format(**locals()))
			return flask.render_template("user/create_token.html", title = "Create User Authentication Token", user = user)

	return flask.abort(405)


def delete_token(user_identifier, token_identifier):
	try:
		service_client.post("/user/{user_identifier}/token/{token_identifier}/delete".format(**locals()))
		flask.flash("Token '%s' was deleted successfully." % token_identifier, "success")
	except requests.HTTPError as exception:
		flask.flash("Token '%s' could not be deleted: %s." % (token_identifier, helpers.get_error_message(exception.response.status_code)), "error")
	return flask.redirect(flask.url_for("user_controller.show", user_identifier = user_identifier))
