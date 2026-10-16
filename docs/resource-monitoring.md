# Server resources

The **Server resources** section uses read-only Linux `/proc`, `ps`, filesystem capacity, and retained sysstat files. It makes no broker requests. Refresh runs every 30 seconds only while the section and browser tab are visible. Server snapshots are cached for 15 seconds, and sysstat history for five minutes.

The `resources` section permission controls access; administrators have access. User Master lists the feature and existing sidebar visibility settings apply. Adding the feature preserves saved choices for all existing sections. A hidden section does not poll. The API independently checks the authenticated user's feature assignment.

CPU work excludes I/O wait and hypervisor steal. All live CPU percentages use all cores as the denominator; process CPU is a lifetime average with one core as 100%. Live memory is total minus available, while sysstat memory follows the installed sysstat definition. Disk capacity has no historical series. Historical CPU values are interval averages, and RAM values are snapshots; neither guarantees the maximum instantaneous usage.

## Deployment status

Deployed to the main Sector Pulse dashboard on 14 October 2026 at 23:58 IST with explicit restart approval. The main `sector-heatmap.service` was restarted; account workers were not restarted. Hosted-only source changes were preserved by comparing the staged base with the running source before installing the five files.

Verified on the signed-in hosted dashboard: live cards, 630 retained history records, range selection, User Master permission and sidebar controls, hide/save/refresh enforcement, and restored visibility. Unauthenticated HTTP API access returns 401. The deployed resource handler was separately exercised against missing and unassigned identities and returns 403. Existing sidebar/Renko visibility choices and recorded runner activation/status/mode flags matched the pre-deployment snapshot. No runners were rearmed.

Server rollback files are in `/home/trading/sector-heatmap/.private/resource-monitor-backups/20261014T182805Z`. Local visual evidence is `outputs/resource-monitor-stage/hosted.png`. The runtime collector remains read-only and has no broker API or order path.

Chart inspection was deployed on 15 October 2026 without a backend restart. Hover selects the nearest recorded point and displays its full date, time including seconds in IST, resource name and percentage. A crosshair marks the selected sample. Charts also support keyboard focus and Left/Right arrows; Escape hides the tooltip. Hosted CPU and memory pointer inspection and keyboard navigation were verified.
