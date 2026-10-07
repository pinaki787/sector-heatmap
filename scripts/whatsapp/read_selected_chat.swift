// Read-only selected-chat adapter. Never clicks, scrolls, types or sends messages.
import AppKit
import ApplicationServices
import Foundation

func attr(_ e: AXUIElement, _ name: String) -> AnyObject? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(e, name as CFString, &value) == .success else { return nil }
    return value
}
func clean(_ s: String) -> String {
    s.replacingOccurrences(of: "\u{200e}", with: "").replacingOccurrences(of: "\u{200f}", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
}
func str(_ e: AXUIElement, _ name: String) -> String { clean(attr(e,name) as? String ?? "") }
func children(_ e: AXUIElement) -> [AXUIElement] { attr(e,kAXChildrenAttribute) as? [AXUIElement] ?? [] }
func find(_ e: AXUIElement, _ id: String, _ depth: Int = 0) -> AXUIElement? {
    if depth > 30 { return nil }
    if str(e,kAXIdentifierAttribute) == id { return e }
    for c in children(e) { if let found = find(c,id,depth+1) { return found } }
    return nil
}
func texts(_ e: AXUIElement, _ depth: Int = 0) -> [String] {
    if depth > 12 { return [] }
    return [str(e,kAXDescriptionAttribute),str(e,kAXValueAttribute)].filter{ !$0.isEmpty } + children(e).flatMap{texts($0,depth+1)}
}
func output(_ result: [String:Any]) { if let data = try? JSONSerialization.data(withJSONObject:result), let s=String(data:data,encoding:.utf8) { print(s) } }
func fail(_ message: String) -> Never { output(["error":message]); exit(0) }

// Initialize AppKit before querying native applications and Accessibility.
_ = NSApplication.shared

let group = CommandLine.arguments.dropFirst().first ?? ""
if group.isEmpty { fail("An exact group name is required.") }
if !AXIsProcessTrusted() { fail("Grant Accessibility permission to the dashboard launcher in System Settings > Privacy & Security > Accessibility, then retry Start. No permission is requested automatically.") }
guard let app=NSWorkspace.shared.runningApplications.first(where: { $0.bundleIdentifier == "net.whatsapp.WhatsApp" }) else { fail("Open the signed-in native WhatsApp app and select the configured group.") }
let root=AXUIElementCreateApplication(app.processIdentifier)
guard let header=find(root,"NavigationBar_HeaderViewButton"), str(header,kAXDescriptionAttribute)==group,
      let table=find(root,"ChatMessagesTableView"), str(table,kAXDescriptionAttribute)=="Messages in chat with \(group)" else { fail("Source mismatch: open the exact configured WhatsApp group. No other chat was ingested.") }
// The native Accessibility tree exposes chat-level unread indicators, but no
// authoritative per-message unread identity or latest-unread marker. Do not
// read message bodies or infer unread state from visibility, clock time, or
// the app's processed-ID database. Preserve WhatsApp's read state.
fail("Selected group verified, but native WhatsApp does not expose authoritative per-message unread state or latest-unread identity. No message bodies were read. A source exposing unread message IDs and full timestamps is required.")
