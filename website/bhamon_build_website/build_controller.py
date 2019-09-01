# pylint: disable=unused-argument

import logging

import flask

import bhamon_build_website.helpers as helpers
import bhamon_build_website.service_client as service_client


logger = logging.getLogger("BuildController")


def build_collection_index():
	query_parameters = {
		"job": helpers.none_if_empty(flask.request.args.get("job", default = None)),
		"worker": helpers.none_if_empty(flask.request.args.get("worker", default = None)),
		"status": helpers.none_if_empty(flask.request.args.get("status", default = None)),
	}

	item_total = service_client.get("/build_count", query_parameters)
	pagination = helpers.get_pagination(item_total)

	query_parameters.update({
		"skip": (pagination["page_number"] - 1) * pagination["item_count"],
		"limit": pagination["item_count"],
		"order_by": [ "update_date descending" ],
	})

	view_data = {
		"build_collection": service_client.get("/build_collection", query_parameters),
		"job_collection": service_client.get("/job_collection", { "limit": 1000, "order_by": [ "identifier ascending" ] }),
		"worker_collection": service_client.get("/worker_collection", { "limit": 1000, "order_by": [ "identifier ascending" ] }),
		"status_collection": _get_status_collection(),
		"pagination": pagination,
	}

	return flask.render_template("build/collection.html", title = "Builds", **view_data)


def build_index(build_identifier):
	view_data = {
		"build": service_client.get("/build/{build_identifier}".format(**locals())),
		"build_steps": service_client.get("/build/{build_identifier}/step_collection".format(**locals())),
		"build_results": service_client.get("/build/{build_identifier}/results".format(**locals())),
		"build_tasks": service_client.get("/build/{build_identifier}/tasks".format(**locals()), { "limit": 10, "order_by": [ "update_date descending" ] }),
	}

	return flask.render_template("build/index.html", title = "Build " + view_data["build"]["identifier"][:18], **view_data)


def build_step_log(build_identifier, step_index):
	log_response = service_client.raw_get("/build/{build_identifier}/step/{step_index}/log".format(**locals()))
	return flask.Response(log_response.text, mimetype = "text/plain")


def abort_build(build_identifier):
	parameters = flask.request.form
	service_client.post("/build/{build_identifier}/abort".format(**locals()), parameters)
	return flask.redirect(flask.request.referrer or flask.url_for("build_collection_index"))


def download_build_archive(build_identifier):
	archive_response = service_client.raw_get("/build/{build_identifier}/download".format(**locals()))
	return flask.Response(archive_response.content,
		headers = { "Content-Disposition": archive_response.headers["Content-Disposition"] },
		mimetype = archive_response.headers["Content-Type"])


def _get_status_collection():
	return [ "pending", "running", "succeeded", "failed", "exception", "aborted", "cancelled" ]
