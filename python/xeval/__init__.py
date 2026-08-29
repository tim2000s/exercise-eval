"""Evaluation of exercise sessions in type 1 diabetes.

The package runs under Pyodide in the browser and unmodified under CPython, so it carries no
dependency the browser cannot supply and no import that touches the filesystem or the network.
Everything it needs arrives as plain dictionaries from the JavaScript side.

Modules, in dependency order:

    units        conversion between mmol/L and mg/dL, and the arithmetic that has to happen in
                 one of them rather than the other
    sources      the bibliography, with the study design and population behind each number
    guidelines   the published numbers themselves, each carrying the source it came from
    intensity    what the heart rate says about how hard a session actually was
    insulin      insulin on board, and what was done to basal and bolus around a session
    evaluate     what happened to glucose, measured rather than assumed
    recommend    what the guidelines say should have been done, and what to change next time
    report       assembly of the above into the structure the page renders
"""

__version__ = "0.1.0"
