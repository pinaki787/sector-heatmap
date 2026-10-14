# Navigation and visibility contract

Every new dashboard section must have a stable key in FEATURES in
sector_heatmap/section_permissions.py. That registry supplies both global
visibility controls and per-user assignments.

Navigation must use data-view or data-feature with the registered key.
Unregistered entries remain hidden, including for administrators. Global
visibility applies to administrators as well; User Master remains administrator-only.
Do not add a navigation shortcut outside this mechanism.

Visibility is not authorization. Account ownership and strategy/API permission
checks must still run on every backend request. Runner Jobs filters its inventory
by permitted strategy sections and never grants access to another user's account.

Before shipping a section, verify global hiding, per-user assignment, direct
route permissions, and administrator-only restrictions where applicable.
