import logging

import flask

import bhamon_orchestra_website.helpers as helpers
import bhamon_orchestra_website.service_client as service_client


logger = logging.getLogger("ScheduleController")


def show_collection(project_identifier):
	query_parameters = {
		"job": helpers.none_if_empty(flask.request.args.get("job", default = None)),
	}

	item_total = service_client.get("/project/{project_identifier}/schedule_count".format(**locals()), query_parameters)
	pagination = helpers.get_pagination(item_total, { "project_identifier": project_identifier, **query_parameters })

	query_parameters.update({
		"skip": (pagination["page_number"] - 1) * pagination["item_count"],
		"limit": pagination["item_count"],
		"order_by": [ "identifier ascending" ],
	})

	view_data = {
		"project": service_client.get("/project/{project_identifier}".format(**locals())),
		"job_collection": service_client.get("/project/{project_identifier}/job_collection".format(**locals()), { "limit": 1000, "order_by": [ "identifier ascending" ] }),
		"schedule_collection": service_client.get("/project/{project_identifier}/schedule_collection".format(**locals()), query_parameters),
		"pagination": pagination,
	}

	helpers.add_display_names([ view_data["project"] ], view_data["job_collection"], [], view_data["schedule_collection"], [])

	return flask.render_template("schedule/collection.html", title = "Schedules", **view_data)


def show(project_identifier, schedule_identifier): # pylint: disable = unused-argument
	view_data = {
		"project": service_client.get("/project/{project_identifier}".format(**locals())),
		"schedule": service_client.get("/project/{project_identifier}/schedule/{schedule_identifier}".format(**locals())),
	}

	view_data["schedule"]["project_display_name"] = view_data["project"]["display_name"]

	job_route = "/project/{project_identifier}/job/{job_identifier}".format(project_identifier = project_identifier, job_identifier = view_data["schedule"]["job"])
	job = service_client.get_or_default(job_route, default_value = {})
	view_data["schedule"]["job_display_name"] = job.get("display_name", view_data["schedule"]["job"])

	return flask.render_template("schedule/index.html", title = "Schedule " + schedule_identifier, **view_data)


def enable(project_identifier, schedule_identifier): # pylint: disable = unused-argument
	service_client.post("/project/{project_identifier}/schedule/{schedule_identifier}/enable".format(**locals()))
	return flask.redirect(flask.request.referrer or flask.url_for("schedule_controller.show_collection", project_identifier = project_identifier))


def disable(project_identifier, schedule_identifier): # pylint: disable = unused-argument
	service_client.post("/project/{project_identifier}/schedule/{schedule_identifier}/disable".format(**locals()))
	return flask.redirect(flask.request.referrer or flask.url_for("schedule_controller.show_collection", project_identifier = project_identifier))
