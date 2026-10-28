"""Print the Agent Runtime class_methods spec for meeting_briefing_agent.agent_app.

Agent Runtime needs the list of callable methods (stream_query,
async_stream_query, ...) when deploying from source. The Python SDK
generates it at deploy time; Terraform has to be given it explicitly.
"""

import json
import sys

import vertexai
from vertexai._genai import _agent_engines_utils as utils

# AdkApp resolves the project on construction; a placeholder keeps this
# offline. Nothing is called on Google Cloud.
vertexai.init(project="class-methods-generator", location="us-central1")

from meeting_briefing_agent.agent_app import app  # noqa: E402

specs = utils._generate_class_methods_spec_or_raise(
    agent=app, operations=app.register_operations()
)
json.dump([utils._to_dict(spec) for spec in specs], sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
