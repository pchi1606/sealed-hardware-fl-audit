"""TEE-hosted DP synthetic data generation for AGSA / OmniEnt (Circle-to-Search).

Prototype migration of Circle-to-Search's federated-analytics pipeline
(`//quality/ui/analysis/search/omnient/federatedanalytics`) from its current
two-stage flow -- Brella FedSQL DP marginals plus offline DP Synth
post-processing (`synthetic_data_postprocessing.py`) -- to a single end-to-end
`TabularSynthesizer` workload that runs entirely inside one Trusted Execution
Environment and releases the synthetic table as a CSV blob.

This reads Circle-to-Search's already-deployed Brella SQL data-upload task
(`:upload` / `upload_query.sql`) directly, with no on-device or collection
changes. Each client uploads one `FcCheckpoint` holding one 1-D tensor per
output column, keyed `upload_query/<column>` (e.g.
`upload_query/first_package_name`). The columns are `first_package_name` (a
UTF-8 string) and `has_interaction`, `is_onboarding_shown_at_invocation`, and
`first_interaction_type` (int64); a client contributes one entry per
`ExampleStore` row. The program stacks every client's columns into a
`pandas.DataFrame`, runs DP Synth's `TabularSynthesizer` with a
`DirectMechanism`, and releases the synthetic table as a CSV blob.

Design choices for this prototype:

  * **User-level DP.** `_load_dataframe` subsamples each client to
    `_MAX_RECORDS_PER_USER` rows, so record-level noise already gives user-level
    DP. This is currently 1 (vs the FedSQL path's `@{L_1=3}`) because the TEE
    container's dpsynth predates `experimental_max_records_per_user`; see
    `_build_synthesizer`.
  * **`first_package_name` is a closed `CategoricalAttribute`** over a fixed
    package allowlist plus an `"other"` bucket. An `OpenSetCategoricalAttribute`
    would DP-discover the package domain inside the TEE; we instead fix the
    allowlist ahead of time to match the FedSQL pipeline's domain.
  * **`DirectMechanism` measures exactly the marginals Circle-to-Search measures
    today** (one per `*_server_query.sql`), so both pipelines measure the same
    set of marginals and can be compared apples-to-apples.
"""

from typing import Any

from dpsynth import constraints
from dpsynth import data_generation_v3
from dpsynth import discrete_mechanisms
from dpsynth import domain
from dpsynth.discrete_mechanisms import accounting
import mbi
import numpy as np
import pandas as pd

# Short column aliases.
_PKG = "first_package_name"
_INTERACT = "has_interaction"
_ONBOARD = "is_onboarding_shown_at_invocation"
_TYPE = "first_interaction_type"

# Interaction-type codes; -1 is unknown.
# LINT.IfChange(OmnientInteractionAppFlowStartEvents)
_NO_INTERACTION = 0
_POSSIBLE_FIRST_INTERACTION_TYPES = [-1, 103, 113, 114, 125, 142, 175, 176]
_INTERACTION_TYPES = [-1, 103, 113, 114, 115, 123, 124, 125, 142, 143, 175, 176]
# LINT.ThenChange(//depot/google3/quality/ui/analysis/search/omnient/federatedanalytics/per_client_first_interaction_type.textproto:OmnientInteractionAppFlowStartEvents)

# LINT.IfChange(OmnientFirstPackageNames)
_PACKAGE_NAMES = (
    "com.whatsapp",
    "com.instagram.android",
    "com.google.android.apps.messaging",
    "com.facebook.katana",
    "com.google.android.youtube",
    "com.android.chrome",
    "jp.naver.line.android",
    "com.twitter.android",
    "com.zhiliaoapp.musically",
    "com.facebook.orca",
    "com.google.android.gm",
    "com.snapchat.android",
    "com.discord",
    "com.google.android.dialer",
    "com.spotify.music",
    "com.google.android.apps.photos",
    "com.google.android.apps.maps",
    "com.reddit.frontpage",
    "com.amazon.mShop.android.shopping",
    "org.telegram.messenger",
    "com.google.android.keep",
    "com.google.android.calculator",
    "com.ss.android.ugc.trill",
    "com.verizon.messaging.vzmsgs",
    "com.nytimes.crossword",
    "com.microsoft.office.outlook",
    "com.nianticlabs.pokemongo",
    "com.google.android.calendar",
    "com.android.settings",
    "com.google.android.apps.youtube.music",
    "org.thoughtcrime.securesms",
    "com.google.android.apps.docs",
    "com.google.android.GoogleCamera",
    "com.andrewshu.android.reddit",
    "com.google.android.apps.docs.editors.docs",
    "com.android.vending",
    "jp.co.yahoo.android.yjtop",
    "com.google.android.deskclock",
    "com.kouzoh.mercari",
    "com.Slack",
    "com.pinterest",
    "com.duolingo",
    "com.ebay.mobile",
    "com.espn.fantasy.lm.football",
    "com.linkedin.android",
    "com.tencent.mm",
    "com.yahoo.mobile.client.android.fantasyfootball",
    "com.microsoft.teams",
    "com.tinder",
    "com.whatsapp.w4b",
    "com.netflix.mediaclient",
    "com.yahoo.mobile.client.android.mail",
    "com.peoplefun.wordcross",
    "com.amazon.mp3",
    "jp.co.mixi.monsterstrike",
    "com.google.android.apps.translate",
    "co.hinge.app",
    "org.mozilla.firefox",
    "com.brave.browser",
    "com.bumble.app",
    "com.amazon.kindle",
    "com.google.android.googlequicksearchbox",
    "com.sec.android.app.launcher",
    "com.sec.android.gallery3d",
    "com.sec.android.app.sbrowser",
    "com.openai.chatgpt",
    "com.sec.android.app.camera",
    "com.kakao.talk",
    "com.google.android.apps.nexuslauncher",
    "com.instagram.barcelona",
    "com.miui.home",
    "com.android.launcher",
    "com.samsung.android.app.notes",
    "com.samsung.android.dialer",
    "com.android.launcher3",
    "com.roblox.client",
    "com.motorola.launcher3",
    "com.samsung.android.incallui",
    "com.samsung.android.messaging",
)
# LINT.ThenChange(//depot/google3/quality/ui/analysis/search/omnient/federatedanalytics/per_client_first_package_name.textproto)
_OTHER_PACKAGE = "other"

_FIRST_PACKAGE_NAME = domain.CategoricalAttribute(
    possible_values=list(_PACKAGE_NAMES) + [_OTHER_PACKAGE],
    out_of_domain_index=len(_PACKAGE_NAMES),
)
_HAS_INTERACTION = domain.CategoricalAttribute(possible_values=[0, 1])
_IS_ONBOARDING_SHOWN = domain.CategoricalAttribute(possible_values=[0, 1])
_FIRST_INTERACTION_TYPE = domain.CategoricalAttribute(
    possible_values=[_NO_INTERACTION] + _INTERACTION_TYPES
)

_COLUMNS = (
    _PKG,
    _INTERACT,
    _ONBOARD,
    _TYPE,
)

# Must match C2S's upload_query.sql; see federatedanalytics/BUILD.
_UPLOAD_QUERY_NAME = "upload_query"

_DOMAINS: dict[str, domain.AttributeType] = {
    _PKG: _FIRST_PACKAGE_NAME,
    _INTERACT: _HAS_INTERACTION,
    _ONBOARD: _IS_ONBOARDING_SHOWN,
    _TYPE: _FIRST_INTERACTION_TYPE,
}

_CONSTRAINTS = (
    # has_interaction == 0 iff no interaction; any interaction type implies 1.
    constraints.Constraint(
        attribute_names=(_INTERACT, _TYPE),
        attribute_domains=(_HAS_INTERACTION, _FIRST_INTERACTION_TYPE),
        possible_combinations=(
            [(0, _NO_INTERACTION)] + [(1, i) for i in _INTERACTION_TYPES]
        ),
    ),
    constraints.Constraint(
        attribute_names=(_TYPE,),
        attribute_domains=(_FIRST_INTERACTION_TYPE,),
        possible_combinations=[
            (v,) for v in [_NO_INTERACTION] + _POSSIBLE_FIRST_INTERACTION_TYPES
        ],
    ),
)

_MAX_ZCDP = 0.416

# Current PWG guidance requires per-query epsilon = 1.0 and per-query
# delta < 0.001, applied to the specific set of maginal queries listed below.
# As an added defense-in-depth measure, we also check that the total ZCDP across
# the entire composition is bounded by an appropriate threshold (overridden at
# build time by the trusted program).  However, the ZCDP alone is not sufficient
# to characterize the PWG agreement, and transparency of the source code is the
# primary mechanism by which an auditor can verify the agreement is met.

_MARGINAL_QUERIES: list[tuple[str, ...]] = [
    (_INTERACT, _TYPE),  # interactions_dp
    (_INTERACT, _ONBOARD, _TYPE),  # interactions
    (_INTERACT, _ONBOARD),  # abandonments
    (_TYPE,),  # first_interaction_type
    (_PKG, _INTERACT, _TYPE, _ONBOARD),  # interactions_per_app (closed set)
    (_PKG, _INTERACT, _ONBOARD),  # abandonments_per_app (closed set)
    (_PKG,),  # invocations_per_app (closed set)
]

_PER_QUERY_EPSILON = 1.0
_PER_QUERY_DELTA = 1e-3
_PER_QUERY_RHO = accounting.zcdp_rho(_PER_QUERY_EPSILON, _PER_QUERY_DELTA)

# DirectMechanism measures multiple queries, splitting budget evenly among them.
# This is an implementation detail of dpsynth and not part of the API contract,
# auditors of this code can verify that the version of dpsynth being used
# splits the budget this way.
# TODO: b/542787826 - Modify PWG agreement to reflect an overall privacy budget,
# rather than per-query budget, which is not well-accepted by the DP community.
_ZCDP_RHO = len(_MARGINAL_QUERIES) * _PER_QUERY_RHO

if _ZCDP_RHO > _MAX_ZCDP:
  raise ValueError("The total zcdp required exceeds the allowed value.")

_MAX_RECORDS_PER_USER = 1
_PGM_ITERS = 5000


def _load_dataframe(
    external_handle: Any, rng: np.random.Generator
) -> pd.DataFrame:
  """Return a contribution-bounded DataFrame of client data."""
  dfs = []
  for blob_id in external_handle.blob_ids:
    client = external_handle.resolve_blob_id_to_numpy_dict(blob_id)
    df = pd.DataFrame(client)
    if df.shape[0] > _MAX_RECORDS_PER_USER:
      df = df.sample(n=_MAX_RECORDS_PER_USER, replace=False, random_state=rng)
    dfs.append(df)

  result = pd.concat(dfs, ignore_index=True)
  result.columns = result.columns.str.removeprefix(f"{_UPLOAD_QUERY_NAME}/")
  result[_PKG] = result[_PKG].str.decode("utf-8")
  return pd.DataFrame(result[list(_COLUMNS)])


def _build_synthesizer() -> data_generation_v3.TabularSynthesizer:
  """Returns the C2S `TabularSynthesizer` backed by a `DirectMechanism`."""
  mechanism = discrete_mechanisms.DirectMechanism(
      prespecified_marginal_queries=_MARGINAL_QUERIES,
      marginal_oracle=mbi.marginal_oracles.message_passing_shafer_shenoy,
      pgm_iters=_PGM_ITERS,
  )
  return data_generation_v3.TabularSynthesizer(
      domains=_DOMAINS,
      discrete_mechanism=mechanism,
      cross_attribute_constraints=_CONSTRAINTS,
      # TODO: b/542787826 - Pass experimental_max_records_per_user once the TEE
      # container's dpsynth supports it; until then _MAX_RECORDS_PER_USER is 1,
      # so the record-level mechanism noise already provides user-level DP.
  )


def trusted_program(external_handle: Any) -> None:
  """Generates DP synthetic tabular data and releases it as a CSV blob."""
  rng = np.random.default_rng()
  dataframe = _load_dataframe(external_handle, rng)

  synthesizer = _build_synthesizer()
  configured = synthesizer.configure(zcdp_rho=_ZCDP_RHO)

  result = configured(rng, dataframe)

  csv_bytes = result.synthetic_data.to_csv(index=False).encode("utf-8")
  external_handle.release_unencrypted(csv_bytes, "synthetic_data_csv")
