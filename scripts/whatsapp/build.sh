#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p .private
swiftc scripts/whatsapp/read_selected_chat.swift -o .private/whatsapp-reader
chmod 700 .private/whatsapp-reader
printf '%s\n' 'Native read-only WhatsApp reader built. Polling remains stopped.'
