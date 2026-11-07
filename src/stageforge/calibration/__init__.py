"""Color and exposure calibration (ADR-0005): ColorChecker → CCM, grey → EV.

Inert until ``calibration.enabled: true`` in the config — with the
default config the pipeline never imports this package's runtime path
beyond the identity calibrator built by
:func:`stageforge.calibration.step.build_calibrator`.
"""
