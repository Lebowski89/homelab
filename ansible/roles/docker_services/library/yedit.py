#!/usr/bin/python

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# pylint: disable=wrong-import-order,wrong-import-position,unused-import

import contextlib
import copy  # noqa: F401
import fcntl  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import shutil  # noqa: F401
import time  # noqa: F401
from io import StringIO

from ansible.module_utils.basic import AnsibleModule

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "core",
}

DOCUMENTATION = """
---
module: yedit
version_added: "2.7"
short_description: Create, modify, and idempotently manage yaml files.
description:
  - Modify yaml files programmatically.
options:
  state:
    description:
    - State represents whether to create, modify, delete, or list yaml
    required: true
    default: present
    choices: ["present", "absent", "list"]
    aliases: []
  debug:
    description:
    - Turn on debug information.
    required: false
    default: false
    type: bool
    aliases: []
  src:
    description:
    - The file that is the target of the modifications.
    required: false
    aliases: []
  content:
    description:
    - Content represents the yaml content you desire to work with.  This
    - could be the file contents to write or the inmemory data to modify.
    required: false
    aliases: []
  content_type:
    description:
    - The python type of the content parameter.
    required: false
    choices: ['yaml', 'json']
    default: yaml
    aliases: []
  key:
    description:
    - The path to the value you wish to modify. Emtpy string means the top of
    - the document.
    required: false
    default: ''
    aliases: []
  value:
    description:
    - The incoming value of parameter 'key'.
    required: false
    default:
    aliases: []
  edits:
    description:
    - A list of edits to perform.  These follow the same format as a single edit
    required: false
    aliases: []
  value_type:
    description:
    - The python type of the incoming value.
    required: false
    default: ''
    aliases: []
  update:
    description:
    - Whether the update should be performed on a dict/hash or list/array
    - object.
    required: false
    default: false
    aliases: []
    type: bool
  append:
    description:
    - Whether to append to an array/list. When the key does not exist or is
    - null, a new array is created. When the key is of a non-list type,
    - nothing is done.
    required: false
    default: false
    aliases: []
    type: bool
  insert:
    description:
    - Whether to insert to an array/list. When the key does not exist or is
    - null, a new array is created. When the key is of a non-list type,
    - nothing is done.
    required: false
    default: false
    aliases: []
    type: bool
  index:
    description:
    - Used in conjunction with the update or insert parameter.  This will update / insert to a
    - specific index in an array/list.
    required: false
    aliases: []
  curr_value:
    description:
    - Used in conjunction with the update parameter.  This is the current
    - value of 'key' in the yaml file.
    required: false
    default: None
    aliases: []
  curr_value_format:
    description:
    - Format of the incoming current value.
    choices: ["yaml", "json", "str"]
    required: false
    default: yaml
    aliases: []
  backup_ext:
    description:
    - The backup file's appended string.
    required: false
    aliases: []
  backup:
    description:
    - Whether to make a backup copy of the current file when performing an
    - edit.
    required: false
    default: false
    aliases: []
    type: bool
  separator:
    description:
    - The separator being used when parsing strings.
    required: false
    default: '.'
    aliases: []
original author:
- "Kenny Woodson <kwoodson@redhat.com>"
update 2.7 (Daniel Joyce (admin@nosugarmaxtaste.com)):
  - Works with ruamel.yaml 0.18+ (and older ruamel too)
  - Falls back to PyYAML if ruamel not installed
  - Replaces depreciated yaml.safe_load/safe_dump
extends_documentation_fragment: []
"""

EXAMPLES = """
# Simple insert of key, value
- name: insert simple key, value
  yedit:
    src: somefile.yml
    key: test
    value: somevalue
    state: present
# Results:
# test: somevalue

# Multilevel insert of key, value
- name: insert simple key, value
  yedit:
    src: somefile.yml
    key: a.b.c
    value: d
    state: present
# Results:
# a:
#   b:
#     c: d
#
# multiple edits at the same time
- name: perform multiple edits
  yedit:
    src: somefile.yml
    edits:
    - key: a.b.c
      value: d
    - key: a.b.c.d
      value: e
    state: present
# Results:
# a:
#   b:
#     c:
#       d: e
"""

# ruamel.yaml >= 0.18 removed safe_load/safe_dump and changed loader API.
# Support both ruamel.yaml and PyYAML seamlessly.
_RUAMEL = False
_YAMLError = Exception

try:
    from ruamel.yaml import YAML  # type: ignore
    from ruamel.yaml.error import YAMLError as _YAMLError  # type: ignore

    _RUAMEL = True
except Exception:  # pragma: no cover
    import yaml as _pyyaml  # type: ignore
    from yaml import YAMLError as _YAMLError  # type: ignore


def _ruamel_yaml_rt():
    y = YAML(typ="rt")
    # keep original formatting/quotes as much as possible
    with contextlib.suppress(Exception):
        y.preserve_quotes = True
    return y


def _ruamel_yaml_safe():
    # "pure=True" matches the guidance in the exception message and avoids C extensions issues on some platforms
    return YAML(typ="safe", pure=True)


# Singletons (ruamel side)
_RY_RT = _ruamel_yaml_rt() if _RUAMEL else None
_RY_SAFE = _ruamel_yaml_safe() if _RUAMEL else None


def _yaml_safe_load(text):
    if not text:
        return None
    if _RUAMEL:
        return _RY_SAFE.load(text)
    return _pyyaml.safe_load(text)


def _yaml_safe_dump(data, default_flow_style=False):
    if _RUAMEL:
        y = _RY_SAFE
        with contextlib.suppress(Exception):
            y.default_flow_style = default_flow_style
        stream = StringIO()
        y.dump(data, stream)
        return stream.getvalue()
    return _pyyaml.safe_dump(data, default_flow_style=default_flow_style)


def _yaml_round_trip_load(text):
    if not text:
        return None
    if _RUAMEL:
        return _RY_RT.load(text)
    # Best-effort fallback for PyYAML
    return _pyyaml.safe_load(text)


def _yaml_round_trip_dump(data, default_flow_style=False):
    if _RUAMEL:
        y = _RY_RT
        with contextlib.suppress(Exception):
            y.default_flow_style = default_flow_style
        stream = StringIO()
        y.dump(data, stream)
        return stream.getvalue()
    return _pyyaml.safe_dump(data, default_flow_style=default_flow_style)


class YeditException(Exception):
    """Exception class for Yedit"""

    pass


# pylint: disable=too-many-public-methods,too-many-instance-attributes
class Yedit:
    """Class to modify yaml files"""

    re_valid_key = r"(((\[-?\d+\])|([0-9a-zA-Z%s/_-]+)).?)+$"
    re_key = r"(?:\[(-?\d+)\])|([0-9a-zA-Z{}/_-]+)"
    com_sep = set([".", "#", "|", ":"])

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        filename=None,
        content=None,
        content_type="yaml",
        separator=".",
        backup_ext=None,
        backup=False,
    ):
        self.content = content
        self._separator = separator
        self.filename = filename
        self.__yaml_dict = content
        self.content_type = content_type
        self.backup = backup
        self.backup_ext = backup_ext or f".{time.strftime('%Y%m%dT%H%M%S')}"
        self.load(content_type=self.content_type)
        if self.__yaml_dict is None:
            self.__yaml_dict = {}

    @property
    def separator(self):
        """getter method for separator"""
        return self._separator

    @separator.setter
    def separator(self, inc_sep):
        """setter method for separator"""
        self._separator = inc_sep

    @property
    def yaml_dict(self):
        """getter method for yaml_dict"""
        return self.__yaml_dict

    @yaml_dict.setter
    def yaml_dict(self, value):
        """setter method for yaml_dict"""
        self.__yaml_dict = value

    @staticmethod
    def parse_key(key, sep="."):
        """parse the key allowing the appropriate separator"""
        common_separators = list(Yedit.com_sep - set([sep]))
        return re.findall(Yedit.re_key.format("".join(common_separators)), key)

    @staticmethod
    def valid_key(key, sep="."):
        """validate the incoming key"""
        common_separators = list(Yedit.com_sep - set([sep]))
        return re.match(Yedit.re_valid_key.format("".join(common_separators)), key) is not None

    # pylint: disable=too-many-return-statements,too-many-branches
    @staticmethod
    def remove_entry(data, key, index=None, value=None, sep="."):
        """remove data at location key"""
        if key == "" and isinstance(data, dict):
            if value is not None:
                data.pop(value)
            elif index is not None:
                raise YeditException(
                    f"remove_entry for a dictionary does not have an index {index}"
                )
            else:
                data.clear()
            return True

        elif key == "" and isinstance(data, list):
            ind = None
            if value is not None:
                try:
                    ind = data.index(value)
                except ValueError:
                    return False
            elif index is not None:
                ind = index
            else:
                del data[:]

            if ind is not None:
                data.pop(ind)
            return True

        if not (key and Yedit.valid_key(key, sep)) and isinstance(data, (list, dict)):
            return None

        key_indexes = Yedit.parse_key(key, sep)
        for arr_ind, dict_key in key_indexes[:-1]:
            if dict_key and isinstance(data, dict):
                data = data.get(dict_key)
            elif arr_ind and isinstance(data, list) and int(arr_ind) <= len(data) - 1:
                data = data[int(arr_ind)]
            else:
                return None

        if key_indexes[-1][0]:
            if (
                isinstance(data, list) and int(key_indexes[-1][0]) <= len(data) - 1
            ):  # noqa: E501
                del data[int(key_indexes[-1][0])]
                return True

        elif key_indexes[-1][1] and isinstance(data, dict):
            del data[key_indexes[-1][1]]
            return True

    @staticmethod
    def add_entry(data, key, item=None, sep="."):
        """Add an item using key notation a.b.c"""
        if key == "":
            pass
        elif not (key and Yedit.valid_key(key, sep)) and isinstance(data, (list, dict)):
            return None

        key_indexes = Yedit.parse_key(key, sep)
        for arr_ind, dict_key in key_indexes[:-1]:
            if dict_key:
                if (
                    isinstance(data, dict) and dict_key in data and data[dict_key]
                ):  # noqa: E501
                    data = data[dict_key]
                    continue
                elif data and not isinstance(data, dict):
                    raise YeditException(
                        "Unexpected item type found while going through key "
                        + f"path: {key} (at key: {dict_key})"
                    )
                data[dict_key] = {}
                data = data[dict_key]

            elif arr_ind and isinstance(data, list) and int(arr_ind) <= len(data) - 1:
                data = data[int(arr_ind)]
            else:
                raise YeditException(
                    f"Unexpected item type found while going through key path: {key}"
                )

        if key == "":
            data = item

        elif (
            key_indexes[-1][0]
            and isinstance(data, list)
            and int(key_indexes[-1][0]) <= len(data)
        ):  # noqa: E501
            if int(key_indexes[-1][0]) > len(data) - 1:
                data.append(item)
            else:
                data[int(key_indexes[-1][0])] = item

        elif key_indexes[-1][1] and isinstance(data, dict):
            data[key_indexes[-1][1]] = item

        else:
            raise YeditException(f"Error adding to object at path: {key}")

        return data

    @staticmethod
    def get_entry(data, key, sep="."):
        """Get an item using key notation a.b.c"""
        if key == "":
            pass
        elif not (key and Yedit.valid_key(key, sep)) and isinstance(data, (list, dict)):
            return None

        key_indexes = Yedit.parse_key(key, sep)
        for arr_ind, dict_key in key_indexes:
            if dict_key and isinstance(data, dict):
                data = data.get(dict_key)
            elif arr_ind and isinstance(data, list) and int(arr_ind) <= len(data) - 1:
                data = data[int(arr_ind)]
            else:
                return None

        return data

    @staticmethod
    def _write(filename, contents):
        """Actually write the file contents to disk."""
        tmp_filename = filename + ".yedit"
        original_mode = os.stat(filename).st_mode
        fd = os.open(
            tmp_filename,
            flags=(os.O_WRONLY | os.O_CREAT | os.O_TRUNC),
            mode=original_mode,
        )
        with open(fd, "w") as yfd:
            fcntl.flock(yfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yfd.write(contents)
            yfd.flush()
            os.fsync(yfd.fileno())
            fcntl.flock(yfd, fcntl.LOCK_UN)

        os.rename(tmp_filename, filename)
        dfd = None
        try:
            dfd = os.open(
                os.path.join(os.path.realpath("."), os.path.dirname(filename)),
                os.O_DIRECTORY,
            )
            os.fsync(dfd)
        finally:
            if dfd:
                os.close(dfd)

    def write(self):
        """write to file"""
        if not self.filename:
            raise YeditException("Please specify a filename.")

        if self.backup and self.file_exists():
            shutil.copy(self.filename, f"{self.filename}{self.backup_ext}")

        with contextlib.suppress(AttributeError):
            self.yaml_dict.fa.set_block_style()

        if self.content_type == "yaml":
            rendered = _yaml_round_trip_dump(self.yaml_dict, default_flow_style=False)
            Yedit._write(self.filename, rendered)
        elif self.content_type == "json":
            Yedit._write(
                self.filename, json.dumps(self.yaml_dict, indent=4, sort_keys=True)
            )
        else:
            raise YeditException(
                f"Unsupported content_type: {self.content_type}."
                + "Please specify a content_type of yaml or json."
            )

        return (True, self.yaml_dict)

    def read(self):
        """read from file"""
        if self.filename is None or not self.file_exists():
            return None
        with open(self.filename) as yfd:
            return yfd.read()

    def file_exists(self):
        return os.path.exists(self.filename)

    def load(self, content_type="yaml"):
        """load yaml file"""
        contents = self.read()

        if not contents and not self.content:
            return None

        if self.content:
            if isinstance(self.content, dict):
                self.yaml_dict = self.content
                return self.yaml_dict
            elif isinstance(self.content, str):
                contents = self.content

        try:
            if content_type == "yaml" and contents:
                with contextlib.suppress(AttributeError):
                    self.yaml_dict.fa.set_block_style()

                # ruamel: round-trip load; PyYAML: safe_load
                self.yaml_dict = _yaml_round_trip_load(contents)

                with contextlib.suppress(AttributeError):
                    self.yaml_dict.fa.set_block_style()

            elif content_type == "json" and contents:
                self.yaml_dict = json.loads(contents)

        except _YAMLError as err:
            raise YeditException(f"Problem with loading yaml file. {err}") from err

        return self.yaml_dict

    def get(self, key):
        try:
            entry = Yedit.get_entry(self.yaml_dict, key, self.separator)
        except KeyError:
            entry = None
        return entry

    def pop(self, path, key_or_item):
        try:
            entry = Yedit.get_entry(self.yaml_dict, path, self.separator)
        except KeyError:
            entry = None

        if entry is None:
            return (False, self.yaml_dict)

        if isinstance(entry, dict):
            if key_or_item in entry:
                entry.pop(key_or_item)
                return (True, self.yaml_dict)
            return (False, self.yaml_dict)

        elif isinstance(entry, list):
            try:
                ind = entry.index(key_or_item)
            except ValueError:
                return (False, self.yaml_dict)
            entry.pop(ind)
            return (True, self.yaml_dict)

        return (False, self.yaml_dict)

    def delete(self, path, index=None, value=None):
        try:
            entry = Yedit.get_entry(self.yaml_dict, path, self.separator)
        except KeyError:
            entry = None

        if entry is None:
            return (False, self.yaml_dict)

        result = Yedit.remove_entry(self.yaml_dict, path, index, value, self.separator)
        if not result:
            return (False, self.yaml_dict)

        return (True, self.yaml_dict)

    def exists(self, path, value):
        try:
            entry = Yedit.get_entry(self.yaml_dict, path, self.separator)
        except KeyError:
            entry = None

        if isinstance(entry, list):
            return value in entry

        if isinstance(entry, dict):
            if isinstance(value, dict):
                return all(entry.get(k) == v for k, v in value.items())
            return value in entry

        return entry == value

    def append(self, path, value):
        try:
            entry = Yedit.get_entry(self.yaml_dict, path, self.separator)
        except KeyError:
            entry = None

        if entry is None:
            self.put(path, [])
            entry = Yedit.get_entry(self.yaml_dict, path, self.separator)

        if not isinstance(entry, list):
            return (False, self.yaml_dict)

        entry.append(value)
        return (True, self.yaml_dict)

    def insert(self, path, value, index=0):
        try:
            entry = Yedit.get_entry(self.yaml_dict, path, self.separator)
        except KeyError:
            entry = None

        if entry is None:
            self.put(path, [])
            entry = Yedit.get_entry(self.yaml_dict, path, self.separator)

        if not isinstance(entry, list):
            return (False, self.yaml_dict)

        entry.insert(index, value)
        return (True, self.yaml_dict)

    # pylint: disable=too-many-arguments
    def update(self, path, value, index=None, curr_value=None):
        try:
            entry = Yedit.get_entry(self.yaml_dict, path, self.separator)
        except KeyError:
            entry = None

        if isinstance(entry, dict):
            if not isinstance(value, dict):
                raise YeditException(
                    "Cannot replace key, value entry in dict with non-dict type. "
                    + f"value=[{value}] type=[{type(value)}]"
                )
            entry.update(value)
            return (True, self.yaml_dict)

        if isinstance(entry, list):
            ind = None
            if curr_value:
                try:
                    ind = entry.index(curr_value)
                except ValueError:
                    return (False, self.yaml_dict)
            elif index is not None:
                ind = index

            if ind is not None and entry[ind] != value:
                entry[ind] = value
                return (True, self.yaml_dict)

            try:
                entry.index(value)
            except ValueError:
                entry.append(value)
                return (True, self.yaml_dict)

            return (False, self.yaml_dict)

        return (False, self.yaml_dict)

    def put(self, path, value):
        try:
            entry = Yedit.get_entry(self.yaml_dict, path, self.separator)
        except KeyError:
            entry = None

        if entry == value:
            return (False, self.yaml_dict)

        # Prefer a round-trip dump+load copy when possible (keeps ruamel CommentedMap types),
        # otherwise deepcopy.
        try:
            tmp_copy = _yaml_round_trip_load(
                _yaml_round_trip_dump(self.yaml_dict, default_flow_style=False)
            )
        except Exception:
            tmp_copy = copy.deepcopy(self.yaml_dict)

        with contextlib.suppress(AttributeError):
            tmp_copy.fa.set_block_style()

        result = Yedit.add_entry(tmp_copy, path, value, self.separator)
        if result is None:
            return (False, self.yaml_dict)

        if path == "":
            if isinstance(result, (list, dict)):
                self.yaml_dict = result
                return (True, self.yaml_dict)
            return (False, self.yaml_dict)

        self.yaml_dict = tmp_copy
        return (True, self.yaml_dict)

    def create(self, path, value):
        if not self.file_exists():
            try:
                tmp_copy = _yaml_round_trip_load(
                    _yaml_round_trip_dump(self.yaml_dict, default_flow_style=False)
                )
            except Exception:
                tmp_copy = copy.deepcopy(self.yaml_dict)

            with contextlib.suppress(AttributeError):
                tmp_copy.fa.set_block_style()

            result = Yedit.add_entry(tmp_copy, path, value, self.separator)
            if result is not None:
                self.yaml_dict = tmp_copy
                return (True, self.yaml_dict)

        return (False, self.yaml_dict)

    @staticmethod
    def get_curr_value(invalue, val_type):
        if invalue is None:
            return None

        curr_value = invalue
        if val_type == "yaml":
            curr_value = _yaml_safe_load(str(invalue))
        elif val_type == "json":
            curr_value = json.loads(invalue)

        return curr_value

    @staticmethod
    def parse_value(inc_value, vtype=""):
        true_bools = [
            "y",
            "Y",
            "yes",
            "Yes",
            "YES",
            "true",
            "True",
            "TRUE",
            "on",
            "On",
            "ON",
        ]
        false_bools = [
            "n",
            "N",
            "no",
            "No",
            "NO",
            "false",
            "False",
            "FALSE",
            "off",
            "Off",
            "OFF",
        ]

        if isinstance(inc_value, str) and "bool" in vtype:
            if inc_value not in true_bools and inc_value not in false_bools:
                raise YeditException(
                    f"Not a boolean type. str=[{inc_value}] vtype=[{vtype}]"
                )
        elif isinstance(inc_value, bool) and "str" in vtype:
            inc_value = str(inc_value)

        if isinstance(inc_value, str) and inc_value == "":
            pass
        elif isinstance(inc_value, str) and "str" not in vtype:
            try:
                inc_value = _yaml_safe_load(inc_value)
            except Exception as err:
                raise YeditException(
                    "Could not determine type of incoming value. "
                    + f"value=[{type(inc_value)}] vtype=[{vtype}]"
                ) from err

        return inc_value

    @staticmethod
    def process_edits(edits, yamlfile):
        results = []
        for edit in edits:
            value = Yedit.parse_value(edit["value"], edit.get("value_type", ""))
            if edit.get("action") == "update":
                curr_value = Yedit.get_curr_value(
                    Yedit.parse_value(edit.get("curr_value")),
                    edit.get("curr_value_format"),
                )

                rval = yamlfile.update(
                    edit["key"], value, edit.get("index"), curr_value
                )

            elif edit.get("action") == "append":
                rval = yamlfile.append(edit["key"], value)

            elif edit.get("action") == "insert":
                rval = yamlfile.insert(edit["key"], value, edit["index"])

            else:
                rval = yamlfile.put(edit["key"], value)

            if rval[0]:
                results.append({"key": edit["key"], "edit": rval[1]})

        return {"changed": len(results) > 0, "results": results}

    # pylint: disable=too-many-return-statements,too-many-branches
    @staticmethod
    def run_ansible(params):
        yamlfile = Yedit(
            filename=params["src"],
            backup=params["backup"],
            content_type=params["content_type"],
            backup_ext=params["backup_ext"],
            separator=params["separator"],
        )

        state = params["state"]

        if params["src"]:
            rval = yamlfile.load()
            if yamlfile.yaml_dict is None and state != "present":
                return {
                    "failed": True,
                    "msg": "Error opening file [{}].  Verify that the ".format(
                        params["src"]
                    )
                    + "file exists, that it is has correct permissions, and is valid yaml.",
                }

        if state == "list":
            if params["content"]:
                content = Yedit.parse_value(params["content"], params["content_type"])
                yamlfile.yaml_dict = content
            if params["key"]:
                rval = yamlfile.get(params["key"])
            return {"changed": False, "result": rval, "state": state}

        elif state == "absent":
            if params["content"]:
                content = Yedit.parse_value(params["content"], params["content_type"])
                yamlfile.yaml_dict = content

            if params["update"]:
                rval = yamlfile.pop(params["key"], params["value"])
            else:
                rval = yamlfile.delete(params["key"], params["index"], params["value"])

            if rval[0] and params["src"]:
                yamlfile.write()

            return {"changed": rval[0], "result": rval[1], "state": state}

        elif state == "present":
            if params["content"]:
                content = Yedit.parse_value(params["content"], params["content_type"])
                if yamlfile.yaml_dict == content and params["value"] is None:
                    return {
                        "changed": False,
                        "result": yamlfile.yaml_dict,
                        "state": state,
                    }
                yamlfile.yaml_dict = content

            edits = []
            _edit = {}
            if params["value"] is not None:
                _edit["value"] = params["value"]
                _edit["value_type"] = params["value_type"]
                _edit["key"] = params["key"]

                if params["update"]:
                    _edit["action"] = "update"
                    _edit["curr_value"] = params["curr_value"]
                    _edit["curr_value_format"] = params["curr_value_format"]
                    _edit["index"] = params["index"]
                elif params["append"]:
                    _edit["action"] = "append"
                elif params["insert"]:
                    _edit["action"] = "insert"
                    _edit["index"] = params["index"]

                edits.append(_edit)
            elif params["edits"] is not None:
                edits = params["edits"]

            if edits:
                results = Yedit.process_edits(edits, yamlfile)
                if results["changed"] and params["src"]:
                    yamlfile.write()
                return {
                    "changed": results["changed"],
                    "result": results["results"],
                    "state": state,
                }

            if params["src"]:
                rval = yamlfile.write()
                return {"changed": rval[0], "result": rval[1], "state": state}

            return {"changed": False, "result": yamlfile.yaml_dict, "state": state}

        return {"failed": True, "msg": "Unkown state passed"}


def json_roundtrip_clean(js):
    cleaned_json = json.dumps(js, skipkeys=True)
    return json.loads(cleaned_json)


# pylint: disable=too-many-branches
def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(
                default="present", type="str", choices=["present", "absent", "list"]
            ),
            debug=dict(default=False, type="bool"),
            src=dict(default=None, type="str"),
            content=dict(default=None),
            content_type=dict(default="yaml", choices=["yaml", "json"]),
            key=dict(default="", type="str"),
            value=dict(),
            value_type=dict(default="", type="str"),
            update=dict(default=False, type="bool"),
            append=dict(default=False, type="bool"),
            insert=dict(default=False, type="bool"),
            index=dict(default=None, type="int"),
            curr_value=dict(default=None, type="str"),
            curr_value_format=dict(
                default="yaml", choices=["yaml", "json", "str"], type="str"
            ),
            backup=dict(default=False, type="bool"),
            backup_ext=dict(
                default=".{}".format(time.strftime("%Y%m%dT%H%M%S")), type="str"
            ),
            separator=dict(default=".", type="str"),
            edits=dict(default=None, type="list"),
        ),
        mutually_exclusive=[["curr_value", "index"], ["update", "append"]],
        required_one_of=[["content", "src"]],
    )

    if module.params["src"] is not None:
        key_error = False
        edit_error = False

        if module.params["key"] is None:
            key_error = True

        if module.params["edits"] in [None, []]:
            edit_error = True
        else:
            for edit in module.params["edits"]:
                if edit.get("key") in [None, ""]:
                    edit_error = True
                    break

        if key_error and edit_error:
            return module.fail_json(
                failed=True, msg="Empty value for parameter key not allowed."
            )

    rval = json_roundtrip_clean(Yedit.run_ansible(module.params))
    if "failed" in rval and rval["failed"]:
        return module.fail_json(**rval)

    return module.exit_json(**rval)


if __name__ == "__main__":
    main()
