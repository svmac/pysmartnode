import gc
import uasyncio as asyncio
from pysmartnode import config
from sys import platform

__updated__ = "2019-11-02"
__version__ = "0.5"

if config.DEBUG:
    def __printRAM(start, info=""):
        print(info, "Mem free", gc.mem_free(), "diff:", gc.mem_free() - start)
else:
    __printRAM = lambda *_: None


def _checkArgs(d, _log):
    required = ("package", "component")
    for r in required:
        if r not in d:
            _log.error("Missing required value {!r} in component".format(r))
            return False
    return True


def _getKwargs(kwargs):
    if type(kwargs) != dict:
        return {}
    COMPONENTS = config.COMPONENTS
    for key in kwargs:
        arg = kwargs[key]
        if type(arg) == str:
            if arg in COMPONENTS:
                kwargs[key] = COMPONENTS[arg]
    return kwargs


def _getArgs(args):
    if type(args) != list:
        return []
    COMPONENTS = config.COMPONENTS
    for i, arg in enumerate(args):
        if type(arg) == str:
            if arg in COMPONENTS:
                args[i] = COMPONENTS[arg]
    return args


def _checkPackage(data):
    if data["package"].startswith("."):
        data["package"] = "{}{}".format("pysmartnode.components", data["package"])


async def registerComponentsAsync(data, _log):
    for component in data["_order"]:
        registerComponent(component, data[component], _log)
        gc.collect()
        await asyncio.sleep_ms(750 if platform == "esp8266" else 200)
        gc.collect()


def registerComponent(componentname, component, _log):
    gc.collect()
    mem_start = gc.mem_free()
    __printRAM(mem_start)
    res = True
    COMPONENTS = config.COMPONENTS
    version = None
    if componentname in COMPONENTS:
        _log.error("Component {!r} already added".format(componentname))
        # asyncLog would block if no network
    else:
        if _checkArgs(component, _log):
            _checkPackage(component)
            try:
                module = __import__(component["package"], globals(),
                                    locals(), [component["component"]], 0)
            except Exception as e:
                _log.critical(
                    "Error importing package {!s}, error: {!s}".format(component["package"], e))
                module = None
            gc.collect()
            err = False
            if module is not None:
                if hasattr(module, "__version__"):
                    version = getattr(module, "__version__")
                if hasattr(module, "COMPONENT_NAME"):
                    module_name = getattr(module, "COMPONENT_NAME")
                else:
                    module_name = component["package"]
                if hasattr(module, component["component"]):
                    kwargs = _getKwargs(
                        component["constructor_args"]) if "constructor_args" in component and type(
                        component["constructor_args"]) == dict else {}
                    args = _getArgs(
                        component["constructor_args"]) if "constructor_args" in component and type(
                        component["constructor_args"]) == list else []
                    try:
                        obj = getattr(module, component["component"])
                        obj = obj(*args, **kwargs)
                        # only support functions (no coroutines) to prevent network block in user/component code
                    except Exception as e:
                        _log.error(
                            "Error during creation of object {!r}, {!r}, version {!s}: {!s}".format(
                                component["component"], componentname, version, e))
                        obj = None
                        err = True
                    if obj is not None:
                        COMPONENTS[componentname] = obj
                        # _log.info("Added module {!r} version {!s} as component {!r}".format(
                        #    module_name, version, componentname))
                    elif err is False:  # but no obj because no obj got created as component was a function
                        _log.info(
                            "Added module {!s} version {!s}, component {!r} as service".format(
                                module_name, version,
                                componentname))  # function. Prpbably unused since 5.0.0.
                    else:
                        res = False
                else:
                    _log.critical(
                        "error during import of module {!s}".format(component["component"]))
                    res = False
    gc.collect()
    __printRAM(mem_start)
    return res
