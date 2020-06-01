"""
Load confounds generated by fMRIprep.

Authors: Dr. Pierre Bellec, Francois Paugam, Hanad Sharmarke
"""
import pandas as pd
from sklearn.decomposition import PCA


def _add_suffix(params, model):
    """
    Add suffixes to a list of parameters.
    Suffixes includes derivatives, power2 and full
    """
    params_full = params.copy()
    for par in params:
        if (model == "derivatives") or (model == "full"):
            params_full.append(f"{par}_derivative1")
        if (model == "power2") or (model == "full"):
            params_full.append(f"{par}_power2")
        if model == "full":
            params_full.append(f"{par}_derivative1_power2")
    return params_full


def _check_params(confounds_raw, params):
    """Check that specified parameters can be found in the confounds."""
    for par in params:
        if not par in confounds_raw.columns:
            raise ValueError(
                f"The parameter {par} cannot be found in the available confounds. You may want to use a different denoising strategy'"
            )


def _find_confounds(confounds_raw, keywords):
    """Find confounds that contain certain keywords."""
    if not isinstance(keywords, list):
        raise ValueError("keywords should be a list")
    list_confounds = []
    for key in keywords:
        key_found = False
        for col in confounds_raw.columns:
            if key in col:
                list_confounds.append(col)
                key_found = True
        if not key_found:
            raise ValueError(f"could not find any confound with the key {key}")
    return list_confounds


def _load_global(confounds_raw, global_signal):
    """Load the regressors derived from the global signal."""
    global_params = _add_suffix(["global_signal"], global_signal)
    _check_params(confounds_raw, global_params)
    return confounds_raw[global_params]


def _load_wm_csf(confounds_raw, wm_csf):
    """Load the regressors derived from the white matter and CSF masks."""
    wm_csf_params = _add_suffix(["csf", "white_matter"], wm_csf)
    _check_params(confounds_raw, wm_csf_params)
    return confounds_raw[wm_csf_params]


def _load_high_pass(confounds_raw):
    """Load the high pass filter regressors."""
    high_pass_params = _find_confounds(confounds_raw, ["cosine"])
    return confounds_raw[high_pass_params]


def _load_motion(confounds_raw, motion, pca_motion):
    """Load the motion regressors."""
    motion_params = _add_suffix(
        ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"], motion
    )
    _check_params(confounds_raw, motion_params)
    confounds_motion = confounds_raw[motion_params]

    # Optionally apply PCA reduction
    if (pca_motion > 0) and (pca_motion < 1):
        confounds_motion = _pca_motion(confounds_motion, n_components=pca_motion)

    return confounds_motion


def _pca_motion(motion, n_components):
    """Reduce the motion paramaters using PCA."""
    motion = motion.dropna()
    pca = PCA(n_components=n_components)
    motion_pca = pd.DataFrame(pca.fit_transform(motion.values))
    motion_pca.columns = ["motion_pca_" + str(col + 1) for col in motion_pca.columns]
    return motion_pca


def _sanitize_strategy(strategy):
    """Defines the supported denoising strategies."""
    init_strategy = {
        "minimal": ["motion", "high_pass", "wm_csf"],
        "minimal_glob": ["motion", "high_pass", "wm_csf", "global"],
    }
    if isinstance(strategy, str):
        # check that the specified strategy is implemented
        if strategy not in init_strategy.keys():
            raise ValueError(f"strategy {strategy} is not supported")
        strategy = init_strategy[strategy]
    elif isinstance(strategy, list):
        all_confounds = ["motion", "high_pass", "wm_csf", "global"]
        for conf in strategy:
            if not conf in all_confounds:
                raise ValueError(f"{conf} is not a supported type of confounds.")
    else:
        raise ValueError("strategy needs to be a string or a list of strings")
    return strategy


def _confounds2df(confounds_raw):
    """Load raw confounds as a pandas DataFrame."""
    if not isinstance(confounds_raw, pd.DataFrame):
        if "nii" in confounds_raw[-6:]:
            suffix = "_space-" + confounds_raw.split("space-")[1]
            confounds_raw = confounds_raw.replace(
                suffix, "_desc-confounds_regressors.tsv",
            )
        confounds_raw = pd.read_csv(confounds_raw, delimiter="\t", encoding="utf-8")
    return confounds_raw


def _sanitize_confounds(confounds_raw):
    """Make sure the inputs are in the correct format."""
    # we want to support loading a single set of confounds, instead of a list
    # so we hack it
    flag_single = isinstance(confounds_raw, str) or isinstance(
        confounds_raw, pd.DataFrame
    )
    if flag_single:
        confounds_raw = [confounds_raw]

    if not isinstance(confounds_raw, list):
        raise ValueError("Invalid input type")
    return confounds_raw, flag_single


def _load_confounds_single(
    confounds_raw, strategy, motion, pca_motion, wm_csf, global_signal
):
    """Load a single confounds file from fmriprep."""
    # Convert tsv file to pandas dataframe
    confounds_raw = _confounds2df(confounds_raw)
    strategy = _sanitize_strategy(strategy)

    confounds = pd.DataFrame()

    if "motion" in strategy:
        confounds_motion = _load_motion(confounds_raw, motion, pca_motion)
        confounds = pd.concat([confounds, confounds_motion], axis=1)

    if "high_pass" in strategy:
        confounds_high_pass = _load_high_pass(confounds_raw)
        confounds = pd.concat([confounds, confounds_high_pass], axis=1)

    if "wm_csf" in strategy:
        confounds_wm_csf = _load_wm_csf(confounds_raw, wm_csf)
        confounds = pd.concat([confounds, confounds_wm_csf], axis=1)

    if "global" in strategy:
        confounds_global_signal = _load_global(confounds_raw, global_signal)
        confounds = pd.concat([confounds, confounds_global_signal], axis=1)

    return confounds


def load_confounds(
    confounds_raw,
    strategy="minimal",
    motion="full",
    pca_motion=1,
    wm_csf="basic",
    global_signal="basic",
):
    """
    Load confounds from fmriprep

    Parameters
    ----------
    confounds_raw : Pandas Dataframe or path to tsv file(s), optionally as a list.
        Raw confounds from fmriprep

    strategy : string or list of strings
        The strategy used to select a subset of the confounds from fmriprep.
        Available strategies:
        "minimal": ["motion", "high_pass", "wm_csf"]
        "minimal_glob": ["motion", "high_pass", "wm_csf", "global"]
        It is also possible to pass a list of strings, e.g. ["motion", "high_pass"]
        Available confound types:
        "motion" head motion estimates.
        "high_pass" discrete cosines covering low frequencies.
        "wm_csf" confounds derived from white matter and cerebrospinal fluid.
        "global" confounds derived from the global signal.

    motion : string, optional
        Type of confounds extracted from head motion estimates.
        "basic" translation/rotation (6 parameters)
        "power2" translation/rotation + quadratic terms (12 parameters)
        "derivatives" translation/rotation + derivatives (12 parameters)
        "full" translation/rotation + derivatives + quadratic terms + power2d derivatives (24 parameters)

    pca_motion : float 0 <= . <= 1
        If the parameters is strictly comprised between 0 and 1, a principal component
        analysis is applied to the motion parameters, and the number of extracted
        components is set to exceed `pca_motion` percent of the parameters variance.

    wm_csf : string, optional
        Type of confounds extracted from masks of white matter and cerebrospinal fluids.
        "basic" the averages in each mask (2 parameters)
        "power2" averages and quadratic terms (4 parameters)
        "derivatives" averages and derivatives (4 parameters)
        "full" averages + derivatives + quadratic terms + power2d derivatives (8 parameters)

    global_signal : string, optional
        Type of confounds extracted from the global signal.
        "basic" just the global signal (1 parameter)
        "power2" global signal and quadratic term (2 parameters)
        "derivatives" global signal and derivative (2 parameters)
        "full" global signal + derivatives + quadratic terms + power2d derivatives (4 parameters)

    Returns
    -------
    confounds:  pandas DataFrame or list of pandas DataFrame
        A reduced version of fMRIprep confounds based on selected strategy and flags.
    """
    confounds_raw, flag_single = _sanitize_confounds(confounds_raw)
    confounds_out = []
    for file in confounds_raw:
        confounds_out.append(
            _load_confounds_single(
                file,
                strategy=strategy,
                motion=motion,
                pca_motion=pca_motion,
                wm_csf=wm_csf,
                global_signal=global_signal,
            )
        )

    # If a single input was provided,
    # send back a single output instead of a list
    if flag_single:
        confounds_out = confounds_out[0]

    return confounds_out
