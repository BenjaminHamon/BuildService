""" Unit tests for ISerializer implementations """

import datetime

import dateutil.tz
import pytest

from bhamon_orchestra_model.serialization.iserializer import ISerializer
from bhamon_orchestra_model.serialization.json_serializer import JsonSerializer


def list_implementations():
	return [ "json" ]


def instantiate_implementation(implementation: str) -> ISerializer:
	if implementation == "json":
		return JsonSerializer()

	raise ValueError("Unsupported implementation '%s'" % implementation)


@pytest.mark.parametrize("implementation", list_implementations())
def test_simple(implementation):
	""" Test serialization with simple values """

	serializer = instantiate_implementation(implementation)

	all_values = [ 1, 1.0, "text" ]

	for value in all_values:
		serialized_value = serializer.serialize_to_string(value)
		deserialized_value = serializer.deserialize_from_string(serialized_value)

		assert deserialized_value == value


@pytest.mark.parametrize("implementation", list_implementations())
def test_collection(implementation):
	""" Test serialization with collections """

	serializer = instantiate_implementation(implementation)

	all_values = [
		[ 1, 2, 3 ],
		{ "first": 1, "second": 2, "third": 3 },
	]

	for value in all_values:
		serialized_value = serializer.serialize_to_string(value)
		deserialized_value = serializer.deserialize_from_string(serialized_value)

		assert deserialized_value == value


@pytest.mark.parametrize("implementation", list_implementations())
def test_datetime(implementation):
	""" Test serialization with datetimes """

	serializer = instantiate_implementation(implementation)

	all_values = [
		datetime.datetime(2020, 1, 1),
		datetime.datetime(2020, 1, 1, tzinfo = datetime.timezone.utc),
		datetime.datetime(2020, 1, 1, tzinfo = dateutil.tz.UTC),
		datetime.datetime(2020, 1, 1, tzinfo = dateutil.tz.gettz("UTC+1")),
		datetime.datetime(2020, 1, 1, tzinfo = dateutil.tz.gettz("UTC-1")),
	]

	for value in all_values:
		value_as_dict = { "date": value } # The value needs to be a dict for JsonDecoder object_hook

		serialized_value = serializer.serialize_to_string(value_as_dict)
		deserialized_value = serializer.deserialize_from_string(serialized_value)

		assert deserialized_value == value_as_dict


@pytest.mark.parametrize("implementation", list_implementations())
def test_datetime_isoformat(implementation):
	""" Test deserialization with ISO 8601 formats """

	serializer = instantiate_implementation(implementation)

	all_values = [
		{ "raw": datetime.datetime(2020, 1, 1), "isoformat": "2020-01-01T00:00:00" },
		{ "raw": datetime.datetime(2020, 1, 1, tzinfo = datetime.timezone.utc), "isoformat": "2020-01-01T00:00:00Z" },
		{ "raw": datetime.datetime(2020, 1, 1, tzinfo = datetime.timezone.utc), "isoformat": "2020-01-01T00:00:00+00:00" },
		{ "raw": datetime.datetime(2020, 1, 1, tzinfo = dateutil.tz.gettz("UTC+1")), "isoformat": "2020-01-01T00:00:00+01:00" },
		{ "raw": datetime.datetime(2020, 1, 1, tzinfo = dateutil.tz.gettz("UTC-1")), "isoformat": "2020-01-01T00:00:00-01:00" },
	]

	for value in all_values:
		value_as_dict = { "date": value["raw"] } # The value needs to be a dict for JsonDecoder object_hook
		isoformat_as_dict = { "date": value["isoformat"] } # The value needs to be a dict for JsonDecoder object_hook

		serialized_value = serializer.serialize_to_string(isoformat_as_dict)
		deserialized_value = serializer.deserialize_from_string(serialized_value)

		assert deserialized_value == value_as_dict
