import datetime
import re
from typing import Optional

import pytz
from loguru import logger as log
import os
import requests
import json

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.web.client import WebClient

from ultimate_lunch_manager.notification_manager import NotificationManager, add_participating_user, \
    remove_participating_user, add_message_to_participants, get_participants_message, add_user_time_preferences, \
    remove_user_time_preferences, add_user_restaurant_preferences, remove_user_restaurant_preferences

log.level("INFO")

load_dotenv()

SLACK_APP_TOKEN = os.getenv('SLACK_APP_TOKEN')
SLACK_TOKEN_SOCKET = os.getenv('SLACK_TOKEN_SOCKET')
TIME_VALIDATION = re.compile(r"\d\d:\d\d")

app = App(token=SLACK_APP_TOKEN, name="The Ultimate Lunch Manager")

CLIENT: Optional[WebClient] = None
CHANNEL_ID = None
CHANNEL_NAME = None
TIMES = ["", "12:00"]
TIME_ALL_OPTIONS = [
    {
        "text": {
            "type": "plain_text",
            "text": "12:00",
            "emoji": True
        },
        "value": "12:00"
    },
]
TIME_SELECTED_OPTIONS = []
SELECTED_TIME_TO_ADD = {}  # {user: time}
SELECTED_TIME_TO_DELETE = {}  # {user: time}
RESTAURANTS = ["", "Nonna"]
RESTAURANTS_ALL_OPTIONS = [
    {
        "text": {
            "type": "plain_text",
            "text": "Nonna",
            "emoji": True
        },
        "value": "Nonna"
    },
]
RESTAURANTS_SELECTED_OPTIONS = []
SELECTED_RESTAURANT_TO_DELETE = {}  # {user: restaurant}
NOTIFICATION_DAYS = []
NOTIFICATION_DAYS_ALL_OPTIONS = [
    {
        "text": {
            "type": "plain_text",
            "text": "Monday",
            "emoji": True
        },
        "value": "Monday"
    },
    {
        "text": {
            "type": "plain_text",
            "text": "Tuesday",
            "emoji": True
        },
        "value": "Tuesday"
    },
    {
        "text": {
            "type": "plain_text",
            "text": "Wednesday",
            "emoji": True
        },
        "value": "Wednesday"
    },
    {
        "text": {
            "type": "plain_text",
            "text": "Thursday",
            "emoji": True
        },
        "value": "Thursday"
    },
    {
        "text": {
            "type": "plain_text",
            "text": "Friday",
            "emoji": True
        },
        "value": "Friday"
    },
    {
        "text": {
            "type": "plain_text",
            "text": "Saturday",
            "emoji": True
        },
        "value": "Saturday"
    },
    {
        "text": {
            "type": "plain_text",
            "text": "Sunday",
            "emoji": True
        },
        "value": "Sunday"
    }
]
NOTIFICATION_DAYS_SELECTED_OPTIONS = []
PARTICIPANTS_NOTIFICATION_TIME = "08:30"
PARTICIPANTS_NOTIFICATION_TIMEZONE = "Europe/Amsterdam"
COMPUTE_LUNCH_TIME = "11:30"
COMPUTE_LUNCH_TIMEZONE = "Europe/Amsterdam"


def create_times_config_message():
    time_list = "\n- ".join(TIMES)
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Configurations :gear:",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*These are the times already entered:*{time_list}"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Add new time",
                        "emoji": True
                    },
                    "value": "time_config",
                    "action_id": "add_new_time"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Delete a time",
                        "emoji": True
                    },
                    "value": "time_config",
                    "action_id": "delete_time"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Confirm times",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": "time_config",
                    "action_id": "confirm_times"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Delete all",
                        "emoji": True
                    },
                    "style": "danger",
                    "value": "time_config",
                    "action_id": "delete_all_times"
                }
            ]
        }
    ]


def create_restaurants_config_message():
    restaurant_list = "\n- ".join(RESTAURANTS)
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Configurations :gear:",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*These are the restaurant already entered:*{restaurant_list}"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Add new restaurant",
                        "emoji": True
                    },
                    "value": "restaurant_config",
                    "action_id": "add_new_restaurant"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Delete a restaurant",
                        "emoji": True
                    },
                    "value": "restaurant_config",
                    "action_id": "delete_restaurant"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Confirm restaurants",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": "restaurant_config",
                    "action_id": "confirm_restaurants"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Delete all",
                        "emoji": True
                    },
                    "style": "danger",
                    "value": "restaurant_config",
                    "action_id": "delete_all_restaurants"
                }
            ]
        }
    ]


def create_notification_days_config_message():
    if len(NOTIFICATION_DAYS_SELECTED_OPTIONS) > 0:
        checkbox_elements = {
            "type": "checkboxes",
            "options": NOTIFICATION_DAYS_ALL_OPTIONS,
            "initial_options": NOTIFICATION_DAYS_SELECTED_OPTIONS,
            "action_id": "notification_days_selection"
        }
    else:
        checkbox_elements = {
            "type": "checkboxes",
            "options": NOTIFICATION_DAYS_ALL_OPTIONS,
            "action_id": "notification_days_selection"
        }
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Configurations :gear:",
                "emoji": True
            }
        },
        {
            "type": "input",
            "element": checkbox_elements,
            "label": {
                "type": "plain_text",
                "text": "Select the days when the bot will automatically work",
                "emoji": True
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Select all",
                        "emoji": True
                    },
                    "value": "notification_days",
                    "action_id": "notification_days_select_all"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Unselect all",
                        "emoji": True
                    },
                    "value": "notification_days",
                    "action_id": "notification_days_unselect_all"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Confirm",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": "notification_days",
                    "action_id": "confirm_notification_days"
                }
            ]
        }
    ]


def create_select_times_message():
    if len(TIME_SELECTED_OPTIONS) > 0:
        checkbox_elements = {
            "type": "checkboxes",
            "options": TIME_ALL_OPTIONS,
            "initial_options": TIME_SELECTED_OPTIONS,
            "action_id": "time_selection"
        }
    else:
        checkbox_elements = {
            "type": "checkboxes",
            "options": TIME_ALL_OPTIONS,
            "action_id": "time_selection"
        }
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Time selection :clock:",
                "emoji": True
            }
        },
        {
            "type": "input",
            "element": checkbox_elements,
            "label": {
                "type": "plain_text",
                "text": "Select all the times when you are available",
                "emoji": True
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Select all",
                        "emoji": True
                    },
                    "value": "time",
                    "action_id": "time_select_all"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Unselect all",
                        "emoji": True
                    },
                    "value": "time",
                    "action_id": "time_unselect_all"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Confirm",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": "time",
                    "action_id": "confirm_time_selection"
                }
            ]
        }
    ]


def create_select_restaurant_message():
    if len(RESTAURANTS_SELECTED_OPTIONS) > 0:
        checkbox_elements = {
            "type": "checkboxes",
            "options": RESTAURANTS_ALL_OPTIONS,
            "initial_options": RESTAURANTS_SELECTED_OPTIONS,
            "action_id": "restaurants_selection"
        }
    else:
        checkbox_elements = {
            "type": "checkboxes",
            "options": RESTAURANTS_ALL_OPTIONS,
            "action_id": "restaurants_selection"
        }
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Restaurants selection",
                "emoji": True
            }
        },
        {
            "type": "input",
            "element": checkbox_elements,
            "label": {
                "type": "plain_text",
                "text": "Select all the restaurants you prefer",
                "emoji": True
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Select all",
                        "emoji": True
                    },
                    "value": "restaurants",
                    "action_id": "restaurants_select_all"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Unselect all",
                        "emoji": True
                    },
                    "value": "restaurants",
                    "action_id": "restaurants_unselect_all"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Confirm",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": "restaurants",
                    "action_id": "confirm_restaurants_selection"
                }
            ]
        }
    ]


def create_on_board_message():
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "You are participating to train :sunglasses:",
                "emoji": True
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "See selected preferences!",
                        "emoji": True
                    },
                    "value": "train_participation",
                    "action_id": "see_preferences"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Update time preferences!",
                        "emoji": True
                    },
                    "value": "train_participation",
                    "action_id": "update_time_preferences"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Update restaurant preferences!",
                        "emoji": True
                    },
                    "value": "train_participation",
                    "action_id": "update_restaurant_preferences"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Leave the train!",
                        "emoji": True
                    },
                    "style": "danger",
                    "value": "train_participation",
                    "action_id": "leave_train"
                }
            ]
        }
    ]


def create_participants_notification_config_message():
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Configurations :gear:",
                "emoji": True
            }
        },
        {
            "type": "input",
            "element": {
                "type": "timepicker",
                "initial_time": PARTICIPANTS_NOTIFICATION_TIME,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select participants notification time",
                    "emoji": True
                },
                "action_id": "select_participants_notification_time"
            },
            "label": {
                "type": "plain_text",
                "text": "Select participants notification time:",
                "emoji": True
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Confirm",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": "notification_config",
                    "action_id": "confirm_participants_notification_time"
                }
            ]
        }
    ]


def create_compute_lunch_notification_config_message():
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Configurations :gear:",
                "emoji": True
            }
        },
        {
            "type": "input",
            "element": {
                "type": "timepicker",
                "initial_time": COMPUTE_LUNCH_TIME,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select computation lunch notification time",
                    "emoji": True
                },
                "action_id": "select_compute_notification_notification_time"
            },
            "label": {
                "type": "plain_text",
                "text": "Select compute lunch notification time:",
                "emoji": True
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Confirm",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": "notification_config",
                    "action_id": "confirm_compute_notification_notification_time"
                }
            ]
        }
    ]


@app.command("/start")  # TODO: Change command name to be more specific
def repeat_text(ack, respond, command):
    global CHANNEL_ID
    global CHANNEL_NAME
    ack()
    if CHANNEL_ID is None:
        CHANNEL_ID = command["channel_id"]
        CHANNEL_NAME = command["channel_name"]
        user_name = command["user_name"]
        respond(text=f"Bot is started in this channel by {user_name}", response_type="in_channel")
        respond(blocks=create_times_config_message(), response_type="ephemeral")
    elif CHANNEL_ID == command["channel_id"]:
        respond(text="Already running in this channel!\nIf you want to stop use /stop", response_type="ephemeral")
    else:
        respond(text=f"Already running in another channel: {CHANNEL_NAME}\nIf you want to move it use /move",
                response_type="ephemeral")


@app.action("add_new_time")
def handle_add_new_time(ack, body, client: WebClient):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and "response_url" in body:
        default_selected_time = "13:00"
        SELECTED_TIME_TO_ADD[body["user"]["id"]] = default_selected_time
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "Configurations :gear:",
                            "emoji": True
                        }
                    },
                    {
                        "type": "input",
                        "element": {
                            "type": "timepicker",
                            "initial_time": default_selected_time,
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select time",
                                "emoji": True
                            },
                            "action_id": "select_time"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Select time:",
                            "emoji": True
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Add",
                                    "emoji": True
                                },
                                "style": "primary",
                                "value": "time_config",
                                "action_id": "add_selected_time"
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Cancel",
                                    "emoji": True
                                },
                                "style": "danger",
                                "value": "time_config",
                                "action_id": "cancel_time_selection"
                            }
                        ]
                    }
                ]
            }
            )
        )


@app.action("select_time")
def handle_select_time(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    selected_time = None
    if body is not None and "actions" in body and "user" in body and "id" in body["user"]:
        for action in body["actions"]:
            if "type" in action and "selected_time" in action and action["type"] == "timepicker":
                selected_time = action["selected_time"]
                break
        if selected_time is not None:
            SELECTED_TIME_TO_ADD[body["user"]["id"]] = selected_time


@app.action("add_selected_time")
def handle_add_selected_time(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body and \
            "user" in body and \
            "id" in body["user"] and \
            body["user"]["id"] in SELECTED_TIME_TO_ADD:
        selected_time = SELECTED_TIME_TO_ADD.pop(body["user"]["id"])
        if selected_time not in TIMES:
            TIME_ALL_OPTIONS.append({
                "text": {
                    "type": "plain_text",
                    "text": selected_time,
                    "emoji": True
                },
                "value": selected_time
            })
            TIME_ALL_OPTIONS.sort(key=lambda x: x["text"]["text"])
            TIMES.append(selected_time)
            TIMES.sort()
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_times_config_message(),
            }
            )
        )


@app.action("cancel_time_selection")
def handle_cancel_time_selection(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body:

        if "user" in body and \
                "id" in body["user"] and \
                body["user"]["id"] in SELECTED_TIME_TO_ADD:
            _ = SELECTED_TIME_TO_ADD.pop(body["user"]["id"])
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_times_config_message(),
            }
            )
        )


@app.action("delete_time")
def handle_delete_time(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and "response_url" in body:
        options = []
        for time in TIMES:
            if time == "":
                continue
            options.append({
                "text": {
                    "type": "plain_text",
                    "text": time,
                    "emoji": True
                },
                "value": time
            }
            )
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "Configurations :gear:",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Select a time to delete:*"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "static_select",
                                "placeholder": {
                                    "type": "plain_text",
                                    "text": "Select a time",
                                    "emoji": True
                                },
                                "options": options,
                                "action_id": "select_time_to_delete"
                            }
                        ]
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Confirm",
                                    "emoji": True
                                },
                                "style": "primary",
                                "value": "time_config",
                                "action_id": "confirm_time_deletion"
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Cancel",
                                    "emoji": True
                                },
                                "style": "danger",
                                "value": "time_config",
                                "action_id": "cancel_time_deletion"
                            }
                        ]
                    }
                ]
            }
            )
        )


@app.action("select_time_to_delete")
def handle_select_time_to_delete(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    selected_time = None
    if body is not None and "actions" in body and "user" in body and "id" in body["user"]:
        for action in body["actions"]:
            if "type" in action and "selected_option" in action and action["type"] == "static_select":
                if "value" in action["selected_option"]:
                    selected_time = action["selected_option"]["value"]
                break
        if selected_time is not None:
            SELECTED_TIME_TO_DELETE[body["user"]["id"]] = selected_time


@app.action("confirm_time_deletion")
def handle_confirm_time_deletion(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body and \
            "user" in body and \
            "id" in body["user"] and \
            body["user"]["id"] in SELECTED_TIME_TO_DELETE:
        selected_time = SELECTED_TIME_TO_DELETE.pop(body["user"]["id"])
        if selected_time in TIMES:
            TIMES.remove(selected_time)
            # remove selected_time from TIME_ALL_OPTIONS where text: text = selected_time
            for i in range(len(TIME_ALL_OPTIONS)):
                if TIME_ALL_OPTIONS[i]["text"]["text"] == selected_time:
                    TIME_ALL_OPTIONS.pop(i)
                    break
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_times_config_message(),
            }
            )
        )


@app.action("cancel_time_deletion")
def handle_cancel_time_deletion(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body:

        if "user" in body and \
                "id" in body["user"] and \
                body["user"]["id"] in SELECTED_TIME_TO_DELETE:
            _ = SELECTED_TIME_TO_DELETE.pop(body["user"]["id"])
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_times_config_message(),
            }
            )
        )


@app.action("confirm_times")
def handle_confirm_times(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body:
        SELECTED_TIME_TO_DELETE.clear()
        SELECTED_TIME_TO_ADD.clear()
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_restaurants_config_message(),
            }
            )
        )


@app.action("delete_all_times")
def handle_delete_all_times(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    global TIMES
    ack()
    if body is not None and \
            "response_url" in body:

        if "user" in body and \
                "id" in body["user"] and \
                body["user"]["id"] in SELECTED_TIME_TO_DELETE:
            _ = SELECTED_TIME_TO_DELETE.pop(body["user"]["id"])
        TIMES.clear()
        TIMES = [""]
        SELECTED_TIME_TO_DELETE.clear()
        SELECTED_TIME_TO_ADD.clear()
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_times_config_message(),
            }
            )
        )


@app.action("add_new_restaurant")
def handle_add_new_restaurant(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and "response_url" in body:
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "Configurations :gear:",
                            "emoji": True
                        }
                    },
                    {
                        "type": "input",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "restaurant_name"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Insert a restaurant name:",
                            "emoji": True
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Confirm",
                                    "emoji": True
                                },
                                "style": "primary",
                                "value": "time_config",
                                "action_id": "confirm_restaurant_insertion"
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Cancel",
                                    "emoji": True
                                },
                                "style": "danger",
                                "value": "time_config",
                                "action_id": "cancel_restaurant_insertion"
                            }
                        ]
                    }
                ]
            }
            )
        )


@app.action("confirm_restaurant_insertion")
def handle_confirm_restaurant_insertion(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "state" in body and \
            "user" in body and \
            "id" in body["user"] and \
            "values" in body["state"]:
        for value in body["state"]["values"]:
            for inner_value in body["state"]["values"][value]:
                if "restaurant_name" != inner_value:
                    continue
                temp_inner_value_dict = body["state"]["values"][value][inner_value]
                if "value" in temp_inner_value_dict:
                    selected_restaurant = temp_inner_value_dict["value"]
                    if selected_restaurant not in RESTAURANTS:
                        RESTAURANTS_ALL_OPTIONS.append({
                            "text": {
                                "type": "plain_text",
                                "text": selected_restaurant,
                                "emoji": True
                            },
                            "value": selected_restaurant
                        })
                        RESTAURANTS_ALL_OPTIONS.sort(key=lambda x: x["text"]["text"])
                        RESTAURANTS.append(selected_restaurant)
                        RESTAURANTS.sort()
                    break

    requests.post(
        url=body["response_url"],
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "replace_original": "true",
            "blocks": create_restaurants_config_message(),
        }
        )
    )


@app.action("cancel_restaurant_insertion")
def handle_cancel_restaurant_insertion(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body:
        SELECTED_RESTAURANT_TO_DELETE.clear()
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_restaurants_config_message(),
            }
            )
        )


@app.action("delete_restaurant")
def handle_delete_restaurant(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and "response_url" in body:
        options = []
        for restaurant in RESTAURANTS:
            if restaurant == "":
                continue
            options.append({
                "text": {
                    "type": "plain_text",
                    "text": restaurant,
                    "emoji": True
                },
                "value": restaurant
            }
            )
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "Configurations :gear:",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Select a restaurant to delete:*"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "static_select",
                                "placeholder": {
                                    "type": "plain_text",
                                    "text": "Select a restaurant",
                                    "emoji": True
                                },
                                "options": options,
                                "action_id": "select_restaurant_to_delete"
                            }
                        ]
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Confirm",
                                    "emoji": True
                                },
                                "style": "primary",
                                "value": "restaurant_config",
                                "action_id": "confirm_restaurant_deletion"
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Cancel",
                                    "emoji": True
                                },
                                "style": "danger",
                                "value": "restaurant_config",
                                "action_id": "cancel_restaurant_deletion"
                            }
                        ]
                    }
                ]
            }
            )
        )


@app.action("select_restaurant_to_delete")
def handle_select_restaurant_to_delete(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    selected_restaurant = None
    if body is not None and "actions" in body and "user" in body and "id" in body["user"]:
        for action in body["actions"]:
            if "type" in action and "selected_option" in action and action["type"] == "static_select":
                if "value" in action["selected_option"]:
                    selected_restaurant = action["selected_option"]["value"]
                break
        if selected_restaurant is not None:
            SELECTED_RESTAURANT_TO_DELETE[body["user"]["id"]] = selected_restaurant


@app.action("confirm_restaurant_deletion")
def handle_confirm_restaurant_deletion(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body and \
            "user" in body and \
            "id" in body["user"] and \
            body["user"]["id"] in SELECTED_RESTAURANT_TO_DELETE:
        selected_restaurant = SELECTED_RESTAURANT_TO_DELETE.pop(body["user"]["id"])
        if selected_restaurant in RESTAURANTS:
            RESTAURANTS.remove(selected_restaurant)
            # remove selected_restaurant from RESTAURANTS_ALL_OPTIONS where text: text = selected_restaurant
            for i in range(len(RESTAURANTS_ALL_OPTIONS)):
                if RESTAURANTS_ALL_OPTIONS[i]["text"]["text"] == selected_restaurant:
                    RESTAURANTS_ALL_OPTIONS.pop(i)
                    break
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_restaurants_config_message(),
            }
            )
        )


@app.action("cancel_restaurant_deletion")
def handle_cancel_restaurant_deletion(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body:

        if "user" in body and \
                "id" in body["user"] and \
                body["user"]["id"] in SELECTED_RESTAURANT_TO_DELETE:
            _ = SELECTED_RESTAURANT_TO_DELETE.pop(body["user"]["id"])
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_restaurants_config_message(),
            }
            )
        )


@app.action("confirm_restaurants")
def handle_confirm_restaurants(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body:
        SELECTED_RESTAURANT_TO_DELETE.clear()
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_notification_days_config_message(),
            }
            )
        )


@app.action("delete_all_restaurants")
def handle_delete_all_restaurants(ack, body, client):
    global RESTAURANTS
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body:

        if "user" in body and \
                "id" in body["user"] and \
                body["user"]["id"] in SELECTED_RESTAURANT_TO_DELETE:
            _ = SELECTED_RESTAURANT_TO_DELETE.pop(body["user"]["id"])
        RESTAURANTS.clear()
        RESTAURANTS = [""]
        SELECTED_RESTAURANT_TO_DELETE.clear()
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_restaurants_config_message(),
            }
            )
        )


@app.action("notification_days_select_all")
def handle_notification_days_select_all(ack, body, client):
    global NOTIFICATION_DAYS
    global NOTIFICATION_DAYS_SELECTED_OPTIONS
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    NOTIFICATION_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    NOTIFICATION_DAYS_SELECTED_OPTIONS = NOTIFICATION_DAYS_ALL_OPTIONS.copy()
    if body is not None and \
            "response_url" in body:
        SELECTED_RESTAURANT_TO_DELETE.clear()
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_notification_days_config_message(),
            }
            )
        )


@app.action("notification_days_unselect_all")
def handle_notification_days_unselect_all(ack, body, client):
    global NOTIFICATION_DAYS
    global NOTIFICATION_DAYS_SELECTED_OPTIONS
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    NOTIFICATION_DAYS = []
    NOTIFICATION_DAYS_SELECTED_OPTIONS = []
    if body is not None and \
            "response_url" in body:
        SELECTED_RESTAURANT_TO_DELETE.clear()
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_notification_days_config_message(),
            }
            )
        )


@app.action("notification_days_selection")
def handle_notification_days_selection(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "actions" in body:
        for action in body["actions"]:
            if "selected_options" in action:
                NOTIFICATION_DAYS.clear()
                NOTIFICATION_DAYS_SELECTED_OPTIONS.clear()
                for selected_option in action["selected_options"]:
                    day = selected_option["value"]
                    option = {
                        "text": {
                            "type": "plain_text",
                            "text": day,
                            "emoji": True
                        },
                        "value": day
                    }
                    NOTIFICATION_DAYS.append(day)
                    NOTIFICATION_DAYS_SELECTED_OPTIONS.append(option)


@app.action("confirm_notification_days")
def handle_confirm_notification_days(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body:
        NOTIFICATION_DAYS.clear()
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_participants_notification_config_message(),
            }
            )
        )


@app.action("select_participants_notification_time")
def handle_select_participants_notification_time(ack, body, client):
    global PARTICIPANTS_NOTIFICATION_TIME
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "state" in body and \
            "user" in body and \
            "id" in body["user"] and \
            "values" in body["state"]:
        for value in body["state"]["values"]:
            for inner_value in body["state"]["values"][value]:
                if "select_participants_notification_time" != inner_value:
                    continue
                temp_inner_value_dict = body["state"]["values"][value][inner_value]
                if "selected_time" in temp_inner_value_dict:
                    PARTICIPANTS_NOTIFICATION_TIME = temp_inner_value_dict["selected_time"]
                    break


@app.action("confirm_participants_notification_time")
def handle_confirm_participants_notification_time(ack, body, client):
    global PARTICIPANTS_NOTIFICATION_TIMEZONE
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    requests.post(
        url=body["response_url"],
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "replace_original": "true",
            "blocks": create_compute_lunch_notification_config_message(),
        }
        )
    )
    if body is not None and \
            "user" in body and \
            "id" in body["user"]:
        PARTICIPANTS_NOTIFICATION_TIMEZONE = get_timezone_from_user(get_user_info_from_client(
            client=client,
            user_id=body["user"]["id"]
        ))


@app.action("select_compute_notification_notification_time")
def handle_select_compute_notification_notification_time(ack, body, client):
    global COMPUTE_LUNCH_TIME
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "state" in body and \
            "user" in body and \
            "id" in body["user"] and \
            "values" in body["state"]:
        for value in body["state"]["values"]:
            for inner_value in body["state"]["values"][value]:
                if "select_compute_notification_notification_time" != inner_value:
                    continue
                temp_inner_value_dict = body["state"]["values"][value][inner_value]
                if "selected_time" in temp_inner_value_dict:
                    COMPUTE_LUNCH_TIME = temp_inner_value_dict["selected_time"]
                    break


@app.action("confirm_compute_notification_notification_time")
def handle_confirm_compute_notification_notification_time(ack, body, client):
    global COMPUTE_LUNCH_TIMEZONE
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    requests.post(
        url=body["response_url"],
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "delete_original": "true",
        }
        )
    )
    if body is not None and \
            "user" in body and \
            "name" in body["user"] and \
            "id" in body["user"]:
        user_name = body["user"]["name"]
        client.chat_postMessage(
            channel=body["channel"]["id"],
            text=f"Bot has been configured in this channel by {user_name}",
        )
        COMPUTE_LUNCH_TIMEZONE = get_timezone_from_user(get_user_info_from_client(
            client=client,
            user_id=body["user"]["id"]
        ))

    notification_manager = NotificationManager(
        client=CLIENT,
        channel_name=CHANNEL_NAME,
        participants_notification_datetime=convert_time_string_to_utc_datetime(time=PARTICIPANTS_NOTIFICATION_TIME,
                                                                               timezone=PARTICIPANTS_NOTIFICATION_TIMEZONE),
        compute_lunch_datetime=convert_time_string_to_utc_datetime(time=COMPUTE_LUNCH_TIME,
                                                                   timezone=COMPUTE_LUNCH_TIMEZONE)
    )
    notification_manager.run()


def get_user_info_from_client(client, user_id) -> dict:
    user_info = client.users_info(user=str(user_id))
    if user_info and "ok" in user_info and user_info["ok"] == True and "user" in user_info:
        return user_info["user"]
    return {}


def get_timezone_from_user(user: dict) -> str:
    return str(user["tz"]) if user is not None and "tz" in user else PARTICIPANTS_NOTIFICATION_TIMEZONE


def convert_time_string_to_utc_datetime(time: str, timezone: str):
    if not TIME_VALIDATION.match(time):
        raise ValueError('Invalid time string')
    utc_now = datetime.datetime.utcnow()
    date = utc_now.replace(
        hour=int(time.split(":")[0]),
        minute=int(time.split(":")[1]),
        second=0,
        microsecond=0
    )
    date = date - datetime.timedelta(
        seconds=get_seconds_difference_from_timezone_name(timezone)
    )
    return date


def get_seconds_difference_from_timezone_name(timezone: str) -> float:
    nowtz = datetime.datetime.now(pytz.timezone(timezone))
    return nowtz.utcoffset().total_seconds()


@app.action("confirm_train_participation")
def handle_confirm_train_participation(ack, body, client):
    ack()
    if body is not None and \
            "user" in body and \
            "id" in body["user"]:
        user_info = get_user_info_from_client(
            client=client,
            user_id=body["user"]["id"]
        )
        add_participating_user(user_name=user_info["name"], user_id=user_info["id"])
    response = client.chat_postEphemeral(
        channel=CHANNEL_NAME,
        user=body["user"]["id"],
        text="You are participating!",
        blocks=create_select_times_message()
    )


@app.action("confirm_restaurants_preference")
def handle_confirm_train_participation(ack, body, client):
    ack()
    if body is not None and \
            "user" in body and \
            "id" in body["user"]:
        user_info = get_user_info_from_client(
            client=client,
            user_id=body["user"]["id"]
        )
        add_participating_user(user_name=user_info["name"], user_id=user_info["id"])
    response = client.chat_postMessage(
        channel=body["user"]["id"],
        user=body["user"]["id"],
        text="You are participating!",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "You are participating to train :sunglasses:",
                    "emoji": True
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Leave the train!",
                            "emoji": True
                        },
                        "style": "danger",
                        "value": "train_participation",
                        "action_id": "leave_train"
                    }
                ]
            }
        ]
    )
    if "ok" in response and "ts" in response:
        add_message_to_participants(
            message_ts=response["ts"],
            user_id=body["user"]["id"],
            channel=response["channel"]
        )


@app.action("reject_train_participation")
def handle_reject_train_participation(ack, body, client):
    ack()
    if body is not None and \
            "user" in body and \
            "id" in body["user"]:
        user_info = get_user_info_from_client(
            client=client,
            user_id=body["user"]["id"]
        )
        remove_participating_user(user_name=user_info["name"], user_id=user_info["id"])
    response = client.chat_postMessage(
        channel=body["user"]["id"],
        user=body["user"]["id"],
        text="You are not participating!",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "You are not participating to train :smiling_face_with_tear:",
                    "emoji": True
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Board the train!",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": "train_participation",
                        "action_id": "board_train"
                    }
                ]
            }
        ]
    )
    if "ok" in response and "ts" in response:
        add_message_to_participants(
            message_ts=response["ts"],
            user_id=body["user"]["id"],
            channel=response["channel"]
        )


@app.action("board_train")
def handle_board_train(ack, body, client):
    ack()
    if body is not None and \
            "user" in body and \
            "id" in body["user"]:
        user_info = get_user_info_from_client(
            client=client,
            user_id=body["user"]["id"]
        )
        add_participating_user(user_name=user_info["name"], user_id=user_info["id"])
    participants_message = get_participants_message(user_id=body["user"]["id"])
    client.chat_update(
        channel=participants_message[1],
        user=body["user"]["id"],
        ts=participants_message[0],
        text="You are participating!",
        blocks=create_on_board_message()
    )


@app.action("leave_train")
def handle_leave_train(ack, body, client):
    ack()
    if body is not None and \
            "user" in body and \
            "id" in body["user"]:
        user_info = get_user_info_from_client(
            client=client,
            user_id=body["user"]["id"]
        )
        remove_participating_user(user_name=user_info["name"], user_id=user_info["id"])
    participants_message = get_participants_message(user_id=body["user"]["id"])
    client.chat_update(
        channel=participants_message[1],
        user=body["user"]["id"],
        ts=participants_message[0],
        text="You are not participating!",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "You are not participating to train :smiling_face_with_tear:",
                    "emoji": True
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Board the train!",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": "train_participation",
                        "action_id": "board_train"
                    }
                ]
            }
        ]
    )


@app.action("time_select_all")
def handle_time_select_all(ack, body, client):
    global TIME_SELECTED_OPTIONS
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    for t in TIMES:
        add_user_time_preferences(user_id=body["user"]["id"], time=t)
    TIME_SELECTED_OPTIONS = TIME_ALL_OPTIONS.copy()
    if body is not None and \
            "response_url" in body:
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_select_times_message(),
            }
            )
        )


@app.action("time_unselect_all")
def handle_time_unselect_all(ack, body, client):
    global TIME_SELECTED_OPTIONS
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    TIME_SELECTED_OPTIONS = []
    for t in TIMES:
        remove_user_time_preferences(user_id=body["user"]["id"], time=t)
    if body is not None and \
            "response_url" in body:
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_select_times_message(),
            }
            )
        )


@app.action("time_selection")
def handle_time_selection(ack, body, client):
    global TIME_SELECTED_OPTIONS
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "actions" in body:
        for action in body["actions"]:
            if "selected_options" in action:
                remove_user_time_preferences(user_id=body["user"]["id"])
                TIME_SELECTED_OPTIONS.clear()
                for selected_option in action["selected_options"]:
                    t = selected_option["value"]
                    option = {
                        "text": {
                            "type": "plain_text",
                            "text": t,
                            "emoji": True
                        },
                        "value": t
                    }
                    add_user_time_preferences(user_id=body["user"]["id"], time=t)
                    TIME_SELECTED_OPTIONS.append(option)


@app.action("confirm_time_selection")
def handle_confirm_time(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body:
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_select_restaurant_message(),
            }
            )
        )


@app.action("restaurants_select_all")
def handle_restaurant_select_all(ack, body, client):
    global RESTAURANTS_SELECTED_OPTIONS
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    for r in RESTAURANTS:
        add_user_restaurant_preferences(user_id=body["user"]["id"], restaurant=r)
    RESTAURANTS_SELECTED_OPTIONS = RESTAURANTS_ALL_OPTIONS.copy()
    if body is not None and \
            "response_url" in body:
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_select_restaurant_message(),
            }
            )
        )


@app.action("restaurants_unselect_all")
def handle_restaurant_unselect_all(ack, body, client):
    global RESTAURANTS_SELECTED_OPTIONS
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    RESTAURANTS_SELECTED_OPTIONS = []
    for r in RESTAURANTS:
        remove_user_restaurant_preferences(user_id=body["user"]["id"], restaurant=r)
    if body is not None and \
            "response_url" in body:
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "replace_original": "true",
                "blocks": create_select_restaurant_message(),
            }
            )
        )


@app.action("restaurants_selection")
def handle_restaurant_selection(ack, body, client):
    global RESTAURANTS_SELECTED_OPTIONS
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "actions" in body:
        for action in body["actions"]:
            if "selected_options" in action:
                remove_user_restaurant_preferences(user_id=body["user"]["id"])
                RESTAURANTS_SELECTED_OPTIONS.clear()
                for selected_option in action["selected_options"]:
                    r = selected_option["value"]
                    option = {
                        "text": {
                            "type": "plain_text",
                            "text": r,
                            "emoji": True
                        },
                        "value": r
                    }
                    add_user_restaurant_preferences(user_id=body["user"]["id"], restaurant=r)
                    RESTAURANTS_SELECTED_OPTIONS.append(option)


@app.action("confirm_restaurants_selection")
def handle_confirm_restaurant(ack, body, client):
    global CLIENT
    if CLIENT is None:
        CLIENT = client
    ack()
    if body is not None and \
            "response_url" in body:
        requests.post(
            url=body["response_url"],
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "delete_original": "true",
            }
            )
        )

        response = client.chat_postMessage(
            channel=body["user"]["id"],
            user=body["user"]["id"],
            text="You are participating!",
            blocks=create_on_board_message()
        )
        if "ok" in response and "ts" in response:
            add_message_to_participants(
                message_ts=response["ts"],
                user_id=body["user"]["id"],
                channel=response["channel"]
            )


@app.event("message")
def handle_message_events(body, logger):
    pass



def main():
    handler = SocketModeHandler(app, SLACK_TOKEN_SOCKET)
    handler.start()


if __name__ == "__main__":
    main()
