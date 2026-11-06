//! In-process validation of untrusted model, URL, and transcript data.
//! No networking, filesystem access, model calls, or mutable global state.

use serde_json::{json, value::RawValue, Value};
use std::collections::BTreeMap;
use std::ffi::{c_char, CString};
use std::panic::catch_unwind;

const MAX_SECONDS: f64 = 86_400.0;
const MAX_REQUEST_BYTES: usize = 8 * 1024 * 1024;
const MAX_JSON_DEPTH: usize = 128;

// Match Python str.strip(), including its additional ASCII record separators.
fn trim(text: &str) -> &str {
    text.trim_matches(|c: char| c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c))
}

fn parse_json(text: &str, depth: usize) -> Option<Value> {
    if depth >= MAX_JSON_DEPTH {
        return None;
    }
    // Parse containers as raw children. Direct Value deserialization with
    // arbitrary_precision treats certain reserved object keys as number tokens.
    // Keeping containers explicit preserves those ordinary, untrusted JSON keys
    // while retaining exact number spellings and a bounded nesting depth.
    match text.trim_start().as_bytes().first()? {
        b'{' => {
            let entries: BTreeMap<String, &RawValue> = serde_json::from_str(text).ok()?;
            let mut result = serde_json::Map::new();
            for (key, raw) in entries {
                result.insert(key, parse_json(raw.get(), depth + 1)?);
            }
            Some(Value::Object(result))
        }
        b'[' => {
            let entries: Vec<&RawValue> = serde_json::from_str(text).ok()?;
            entries
                .iter()
                .map(|raw| parse_json(raw.get(), depth + 1))
                .collect::<Option<Vec<_>>>()
                .map(Value::Array)
        }
        _ => serde_json::from_str(text).ok(),
    }
}

pub fn parse_llm_json(text: &str) -> Value {
    let mut text = trim(text);
    if let Some(rest) = text.strip_prefix("```") {
        text = text.split_once('\n').map_or(rest, |(_, body)| body);
        text = trim(text.strip_suffix("```").unwrap_or(text));
    }
    if let Some(value) = parse_json(text, 0) {
        return value;
    }

    // Preserve the existing outermost-fragment fallback and first-start order.
    // Do not silently accept the first of two adjacent objects or arrays.
    let mut candidates = Vec::new();
    for (open, close) in [('{', '}'), ('[', ']')] {
        if let (Some(start), Some(end)) = (text.find(open), text.rfind(close)) {
            if end > start {
                candidates.push((start, &text[start..=end]));
            }
        }
    }
    candidates.sort_by_key(|(start, _)| *start);
    for (_, fragment) in candidates {
        if let Some(value) = parse_json(fragment, 0) {
            return value;
        }
    }
    Value::Null
}

// Unicode 15.1 Nd blocks, matching Python 3.13's decimal-digit database.
// Numeric strings accept these decimal digits, not other numeric characters.
const DECIMAL_ZEROS: &[u32] = &[
    0x30, 0x660, 0x6f0, 0x7c0, 0x966, 0x9e6, 0xa66, 0xae6, 0xb66, 0xbe6, 0xc66, 0xce6, 0xd66,
    0xde6, 0xe50, 0xed0, 0xf20, 0x1040, 0x1090, 0x17e0, 0x1810, 0x1946, 0x19d0, 0x1a80, 0x1a90,
    0x1b50, 0x1bb0, 0x1c40, 0x1c50, 0xa620, 0xa8d0, 0xa900, 0xa9d0, 0xa9f0, 0xaa50, 0xabf0, 0xff10,
    0x104a0, 0x10d30, 0x11066, 0x110f0, 0x11136, 0x111d0, 0x112f0, 0x11450, 0x114d0, 0x11650,
    0x116c0, 0x11730, 0x118e0, 0x11950, 0x11c50, 0x11d50, 0x11da0, 0x11f50, 0x16a60, 0x16ac0,
    0x16b50, 0x1d7ce, 0x1d7d8, 0x1d7e2, 0x1d7ec, 0x1d7f6, 0x1e140, 0x1e2f0, 0x1e4f0, 0x1e950,
    0x1fbf0,
];

fn python_float(text: &str) -> Option<f64> {
    let normalized: String = text
        .trim()
        .chars()
        .map(|ch| {
            let codepoint = ch as u32;
            let index = DECIMAL_ZEROS.partition_point(|zero| *zero <= codepoint);
            if index > 0 && codepoint - DECIMAL_ZEROS[index - 1] < 10 {
                char::from(b'0' + (codepoint - DECIMAL_ZEROS[index - 1]) as u8)
            } else {
                ch
            }
        })
        .collect();
    let bytes = normalized.as_bytes();
    // Python permits underscores only between decimal digits, including in the
    // exponent. Validate placement before removing them for Rust's converter.
    for (index, &byte) in bytes.iter().enumerate() {
        if byte == b'_'
            && (index == 0
                || index + 1 == bytes.len()
                || !bytes[index - 1].is_ascii_digit()
                || !bytes[index + 1].is_ascii_digit())
        {
            return None;
        }
    }
    normalized.replace('_', "").parse().ok()
}

fn number(value: &Value) -> Option<f64> {
    match value {
        Value::Number(n) => n.as_f64().or_else(|| n.to_string().parse().ok()),
        Value::String(s) => python_float(s),
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        _ => None,
    }
}

fn timestamp(value: &Value, max_duration: f64) -> f64 {
    // Python max(0.0, NaN) yields zero; clamp alone would retain NaN.
    let value = number(value).unwrap_or(0.0);
    let mut ts = if value.is_nan() {
        0.0
    } else {
        value.clamp(0.0, MAX_SECONDS)
    };
    if max_duration.is_finite() && max_duration > 0.0 {
        ts = ts.min(max_duration);
    }
    ts
}

fn truncate_claim(text: &str) -> String {
    if text.chars().count() <= 500 {
        return text.to_owned();
    }
    // Count Unicode code points, as Python slicing does, rather than UTF-8 bytes.
    let chars: Vec<char> = text.chars().take(500).collect();
    let end = chars
        .iter()
        .rposition(|c| *c == ' ')
        .filter(|i| *i > 400)
        .unwrap_or(500);
    let mut result: String = chars[..end].iter().collect();
    result.push('…');
    result
}

pub fn normalize_claims(text: &str, max_duration: f64, max_claims: usize) -> Value {
    let parsed = parse_llm_json(text);
    let claims = if parsed.is_object() {
        &parsed["claims"]
    } else {
        &parsed
    };
    let Some(items) = claims.as_array() else {
        return json!([]);
    };
    let mut result = Vec::new();
    for item in items {
        if result.len() >= max_claims {
            break;
        }
        let Some(text) = item
            .get("text")
            .and_then(Value::as_str)
            .map(trim)
            .filter(|s| !s.is_empty())
        else {
            continue;
        };
        let category = item
            .get("category")
            .and_then(Value::as_str)
            .filter(|category| matches!(*category, "fact" | "opinion" | "unclear"))
            .unwrap_or("fact");
        result.push(json!({
            "text": truncate_claim(text),
            "timestamp_seconds": timestamp(&item["timestamp_seconds"], max_duration),
            "category": category,
        }));
    }
    // Preserve repeated claims and their order: the previous service did not dedupe.
    Value::Array(result)
}

fn valid_id(value: &str) -> bool {
    value.len() == 11
        && value
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'_' || c == b'-')
}

pub fn extract_video_id(input: &str) -> Option<&str> {
    let input = trim(input);
    if valid_id(input) {
        return Some(input);
    }
    // A deliberately narrow grammar for supported YouTube URLs, not a general URL parser.
    if input
        .chars()
        .any(|c| c.is_whitespace() || c.is_control() || c == '\\')
    {
        return None;
    }
    let rest = if let Some((scheme, rest)) = input.split_once("://") {
        if !scheme.eq_ignore_ascii_case("https") && !scheme.eq_ignore_ascii_case("http") {
            return None;
        }
        rest
    } else {
        input.strip_prefix("//").unwrap_or(input)
    };
    let authority_end = rest.find(['/', '?', '#']).unwrap_or(rest.len());
    let host = rest[..authority_end].to_ascii_lowercase();
    let short = matches!(host.as_str(), "youtu.be" | "www.youtu.be");
    if !short
        && !matches!(
            host.as_str(),
            "youtube.com" | "www.youtube.com" | "m.youtube.com" | "music.youtube.com"
        )
    {
        return None;
    }
    let resource = rest[authority_end..].split('#').next()?;
    let (path, query) = resource.split_once('?').unwrap_or((resource, ""));
    let id = if short {
        path.strip_prefix('/')?
    } else if path == "/watch" {
        let mut ids = query
            .split('&')
            .filter_map(|param| param.split_once('='))
            .filter(|(key, _)| *key == "v")
            .map(|(_, value)| value);
        let id = ids.next()?;
        if ids.next().is_some() {
            return None; // ambiguous video selection
        }
        id
    } else {
        ["/embed/", "/shorts/", "/v/"]
            .iter()
            .find_map(|prefix| path.strip_prefix(*prefix))?
    };
    valid_id(id).then_some(id)
}

pub fn normalize_transcript(entries: &[Value]) -> Value {
    let mut segments = Vec::new();
    let mut text_parts = Vec::new();
    for entry in entries {
        let Some(text) = entry.get("text").and_then(Value::as_str).map(trim) else {
            continue;
        };
        let (Some(start), Some(duration)) = (number(&entry["start"]), number(&entry["duration"]))
        else {
            continue;
        };
        if !start.is_finite()
            || !duration.is_finite()
            || text.is_empty()
            || (text.starts_with('[') && text.ends_with(']'))
        {
            continue;
        }
        segments
            .push(json!({"text": text, "start": start.max(0.0), "duration": duration.max(0.0)}));
        text_parts.push(text);
    }
    // Repeated caption rows can be intentional; retain them, matching the service.
    json!({"segments": segments, "full_text": text_parts.join(" ")})
}

fn format_transcript(entries: &[Value]) -> String {
    entries
        .iter()
        .map(|entry| {
            // Only numeric segment starts were accepted by the original formatter.
            let start = if entry["start"].is_number() || entry["start"].is_boolean() {
                timestamp(&entry["start"], 0.0)
            } else {
                0.0
            } as u64;
            format!(
                "[{:02}:{:02}] {}",
                start / 60,
                start % 60,
                entry["text"].as_str().unwrap_or("")
            )
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn dispatch(request: &Value) -> Result<Value, &'static str> {
    match request["op"].as_str() {
        Some("parse_llm_json") => Ok(request["text"]
            .as_str()
            .map(parse_llm_json)
            .unwrap_or(Value::Null)),
        Some("normalize_claims") => Ok(normalize_claims(
            request["text"].as_str().unwrap_or(""),
            number(&request["max_duration"]).unwrap_or(0.0),
            request["max_claims"]
                .as_u64()
                .unwrap_or(30)
                .try_into()
                .unwrap_or(usize::MAX),
        )),
        Some("extract_video_id") => Ok(json!(request["url"].as_str().and_then(extract_video_id))),
        Some("normalize_transcript") => Ok(normalize_transcript(
            request["entries"].as_array().ok_or("invalid_entries")?,
        )),
        Some("format_transcript") => Ok(json!(format_transcript(
            request["entries"].as_array().ok_or("invalid_entries")?
        ))),
        Some("validate_duration") => {
            let duration = number(&request["duration"])
                .filter(|d| d.is_finite() && *d > 0.0)
                .ok_or("invalid_duration")?;
            let max_duration = number(&request["max_duration"]).ok_or("invalid_duration")?;
            Ok(json!({"duration": duration, "too_long": duration > max_duration}))
        }
        _ => Err("unknown_operation"),
    }
}

fn process(bytes: &[u8]) -> Value {
    match std::str::from_utf8(bytes)
        .ok()
        .and_then(|text| parse_json(text, 0))
    {
        Some(request) => match dispatch(&request) {
            Ok(result) => json!({"result": result}),
            Err(error) => json!({"error": error}),
        },
        None => json!({"error": "invalid_request"}),
    }
}

#[no_mangle]
pub extern "C" fn factcheck_core_abi_version() -> u32 {
    1
}

/// Return an owned JSON response, to be freed exactly once with factcheck_core_free.
///
/// # Safety
/// `data` must point to `len` readable bytes for the duration of this call.
/// A null pointer is accepted as an invalid request. No input pointer is retained.
#[no_mangle]
pub unsafe extern "C" fn factcheck_core_process(data: *const u8, len: usize) -> *mut c_char {
    let result = catch_unwind(|| {
        if data.is_null() || len > MAX_REQUEST_BYTES {
            return json!({"error": "invalid_request"});
        }
        // SAFETY: the caller guarantees a valid input slice; length is bounded above.
        process(unsafe { std::slice::from_raw_parts(data, len) })
    })
    .unwrap_or_else(|_| json!({"error": "internal_error"}));
    // JSON serialization escapes embedded NULs, so CString construction cannot fail.
    CString::new(result.to_string())
        .expect("JSON contains no NUL bytes")
        .into_raw()
}

/// # Safety
/// `data` must be null or an unmodified, not-yet-freed pointer returned by
/// factcheck_core_process. It must never be freed with another allocator.
#[no_mangle]
pub unsafe extern "C" fn factcheck_core_free(data: *mut c_char) {
    if !data.is_null() {
        // SAFETY: ownership of this exact CString allocation is returned by caller.
        drop(unsafe { CString::from_raw(data) });
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // The same synthetic fixtures are exercised through the Python FFI and services.
    #[test]
    fn shared_contract_fixtures() {
        let fixtures = parse_json(include_str!("../../tests/fixtures/processor.json"), 0).unwrap();
        for case in fixtures.as_array().unwrap() {
            let actual = dispatch(&case["request"]);
            if let Some(error) = case["error"].as_str() {
                assert_eq!(actual, Err(error), "{}", case["name"]);
            } else {
                assert_eq!(actual.unwrap(), case["expected"], "{}", case["name"]);
            }
        }
    }

    #[test]
    fn unicode_truncation_and_word_boundary() {
        let long = "界".repeat(600);
        let result = normalize_claims(&json!([{"text": long}]).to_string(), 0.0, 30);
        assert_eq!(result[0]["text"].as_str().unwrap().chars().count(), 501);
        let text = format!("{} {}", "x".repeat(450), "y".repeat(200));
        let result = normalize_claims(&json!([{"text": text}]).to_string(), 0.0, 30);
        assert_eq!(result[0]["text"], format!("{}…", "x".repeat(450)));
    }

    #[test]
    fn ffi_invalid_utf8_and_null_are_errors() {
        for bytes in [&b"\xff"[..], &b"{} trailing"[..]] {
            // SAFETY: live byte slice, returned allocation freed once after reading.
            unsafe {
                let ptr = factcheck_core_process(bytes.as_ptr(), bytes.len());
                let result: Value =
                    serde_json::from_slice(std::ffi::CStr::from_ptr(ptr).to_bytes()).unwrap();
                assert_eq!(result["error"], "invalid_request");
                factcheck_core_free(ptr);
            }
        }
        unsafe {
            let ptr = factcheck_core_process(std::ptr::null(), 0);
            assert!(!ptr.is_null());
            factcheck_core_free(ptr);
            factcheck_core_free(std::ptr::null_mut());
        }
    }
}
