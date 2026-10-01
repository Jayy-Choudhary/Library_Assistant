import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  // Default connection details matching your PythonAnywhere server config
  static String baseUrl = "https://jaychoudhary.pythonanywhere.com";
  static String apiKey = "jay-library-secret-key-2026";

  /// Real-time online/offline indicator for the whole app
  static final ValueNotifier<bool> isOnline = ValueNotifier<bool>(true);

  /// Event triggered whenever the app shifts from Offline -> Online
  /// Screens can listen to this to automatically reload latest data from cloud.
  static final ValueNotifier<int> syncEvent = ValueNotifier<int>(0);

  static Timer? _heartbeatTimer;

  /// Initialize connection settings, start background network monitoring
  static Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    baseUrl = prefs.getString('api_base_url') ?? "https://jaychoudhary.pythonanywhere.com";
    apiKey = prefs.getString('api_key') ?? "jay-library-secret-key-2026";

    // Initial connectivity probe (non-blocking)
    checkConnectivity();

    // Start background heartbeat every 10 seconds to auto-detect online/offline transition
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 10), (_) {
      checkConnectivity();
    });
  }

  /// Update server connection configuration
  static Future<void> updateConnectionSettings(String newUrl, String newKey) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('api_base_url', newUrl);
    await prefs.setString('api_key', newKey);
    baseUrl = newUrl;
    apiKey = newKey;
    await checkConnectivity();
  }

  /// Test connectivity and credentials with specific parameters
  static Future<bool> testConnection(String url, String key) async {
    final uri = Uri.parse("$url/api/db/call");
    final headers = {
      "Content-Type": "application/json",
      "X-API-Key": key,
    };
    final payload = {
      "method": "seat_counts",
      "args": [],
      "kwargs": {},
    };
    try {
      final response = await http.post(
        uri,
        headers: headers,
        body: jsonEncode(payload),
      ).timeout(const Duration(seconds: 4));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Check connectivity to cloud server and transition online/offline state
  static Future<bool> checkConnectivity() async {
    final connected = await testConnection(baseUrl, apiKey);
    _setOnline(connected);
    return connected;
  }

  /// Internal state updater that fires syncEvent on reconnect
  static void _setOnline(bool online) {
    if (isOnline.value != online) {
      final wasOffline = !isOnline.value;
      isOnline.value = online;
      if (wasOffline && online) {
        // App just transitioned from Offline to Online! Notify all active listeners to refresh.
        syncEvent.value++;
      }
    }
  }

  /// Local disk cache helpers
  static Future<void> _saveCache(String key, dynamic data) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(key, jsonEncode(data));
      await prefs.setString('${key}_time', DateTime.now().toIso8601String());
    } catch (_) {}
  }

  static Future<dynamic> _loadCache(String key) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final str = prefs.getString(key);
      if (str != null && str.isNotEmpty) {
        return jsonDecode(str);
      }
    } catch (_) {}
    return null;
  }

  /// Core RPC database executor on the FastAPI cloud backend
  static Future<dynamic> _callDb(String method, {List<dynamic> args = const [], Map<String, dynamic> kwargs = const {}}) async {
    final url = Uri.parse("$baseUrl/api/db/call");
    final headers = {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    };
    
    final payload = {
      "method": method,
      "args": args,
      "kwargs": kwargs,
    };

    try {
      final response = await http.post(
        url,
        headers: headers,
        body: jsonEncode(payload),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode != 200) {
        throw Exception("Server returned error ${response.statusCode}: ${response.body}");
      }

      final data = jsonDecode(response.body);
      if (data is Map && data.containsKey("error")) {
        throw Exception(data["error"]);
      }
      
      _setOnline(true);
      return data["result"];
    } catch (e) {
      _setOnline(false);
      throw Exception("API Connection Failed: $e");
    }
  }

  /// Cached read-through wrapper:
  /// - Online: queries cloud server, updates cache, returns fresh data.
  /// - Offline / Network failure: transparently serves cached local copy.
  static Future<dynamic> _callDbWithCache(
    String cacheKey,
    String method, {
    List<dynamic> args = const [],
    Map<String, dynamic> kwargs = const {},
  }) async {
    // If currently offline, immediately try cache to prevent waiting for a 10s timeout
    if (!isOnline.value) {
      final cached = await _loadCache(cacheKey);
      if (cached != null) {
        return cached;
      }
    }

    try {
      final result = await _callDb(method, args: args, kwargs: kwargs);
      // Save fresh data to local cache
      await _saveCache(cacheKey, result);
      return result;
    } catch (e) {
      // Network call failed: fall back to cache
      final cached = await _loadCache(cacheKey);
      if (cached != null) {
        return cached;
      }
      throw Exception("Offline Mode: No local cache available for this view. Connect to the internet to load fresh data.");
    }
  }

  // ==========================================
  // READ METHODS (Cached for Offline Support)
  // ==========================================

  /// Fetch dashboard counters and lists in 1 batch request
  static Future<Map<String, dynamic>> getDashboardMetrics() async {
    final result = await _callDbWithCache("cache_dashboard_metrics", "get_dashboard_metrics");
    return Map<String, dynamic>.from(result);
  }

  /// List active/old students from database
  static Future<List<dynamic>> getStudents({String filter = "Active"}) async {
    final args = filter == "All" ? [] : [filter];
    final result = await _callDbWithCache(
      "cache_students_$filter",
      "get_all_students",
      args: args,
    );
    return List<dynamic>.from(result);
  }

  /// Search students by query string (works offline via local cache filter!)
  static Future<List<dynamic>> searchStudents(String query) async {
    if (!isOnline.value) {
      // Offline fallback: filter from cached students list
      final cached = await _loadCache("cache_students_All") ?? await _loadCache("cache_students_Active");
      if (cached is List) {
        final q = query.toLowerCase();
        return cached.where((s) {
          final name = (s['full_name'] ?? '').toString().toLowerCase();
          final seat = (s['seat_number'] ?? '').toString().toLowerCase();
          final mobile = (s['mobile_number'] ?? '').toString().toLowerCase();
          return name.contains(q) || seat.contains(q) || mobile.contains(q);
        }).toList();
      }
    }

    final result = await _callDb("search_students", args: [query]);
    return List<dynamic>.from(result);
  }

  /// Fetch detail profile for student
  static Future<Map<String, dynamic>?> getStudentById(int studentId) async {
    final result = await _callDbWithCache(
      "cache_student_$studentId",
      "get_student_by_id",
      args: [studentId],
    );
    return result != null ? Map<String, dynamic>.from(result) : null;
  }

  /// Fetch specific student fee record details
  static Future<Map<String, dynamic>?> getFeeRecord(int studentId) async {
    final result = await _callDbWithCache(
      "cache_fee_record_$studentId",
      "get_fee_record",
      args: [studentId],
    );
    return result != null ? Map<String, dynamic>.from(result) : null;
  }

  /// Fetch payment logs for a student
  static Future<List<dynamic>> getPaymentHistory(int studentId) async {
    final result = await _callDbWithCache(
      "cache_payment_history_$studentId",
      "get_payment_history",
      args: [studentId],
    );
    return List<dynamic>.from(result);
  }

  /// Fetch notices filtered by state (Pending, Due, Overdue, Reminder Due)
  static Future<List<dynamic>> getNoticeCenterRows(String filter) async {
    final result = await _callDbWithCache(
      "cache_notices_$filter",
      "get_notice_center_rows",
      args: [filter],
    );
    return List<dynamic>.from(result);
  }

  /// Fetch general notice template settings
  static Future<String> getGeneralNoticeTemplate() async {
    final result = await _callDbWithCache(
      "cache_notice_template",
      "get_general_notice_template",
    );
    return result?.toString() ?? "";
  }

  /// Fetch all active students with their fee records (for fee management screen)
  static Future<List<dynamic>> getFeesWithStudents() async {
    final result = await _callDbWithCache(
      "cache_fees_with_students",
      "get_fees_with_students",
    );
    return List<dynamic>.from(result);
  }

  /// Get computed fee status for a student (Paid, Reminder Due, Due, Overdue, Cancelled, Active)
  static Future<String> getFeeStatus(int studentId) async {
    final result = await _callDbWithCache(
      "cache_fee_status_$studentId",
      "get_fee_status",
      args: [studentId],
    );
    return result?.toString() ?? "Active";
  }

  /// Fetch analytics data (revenue trends, occupancy, fee status distribution, etc.)
  static Future<Map<String, dynamic>> getAnalyticsData() async {
    final result = await _callDbWithCache(
      "cache_analytics_data",
      "get_analytics_data",
    );
    return Map<String, dynamic>.from(result);
  }

  /// Fetch seats compatible with a target shift type
  static Future<List<String>> getCompatibleSeats(String shiftType) async {
    final result = await _callDbWithCache(
      "cache_compatible_seats_$shiftType",
      "get_compatible_seats",
      args: [shiftType],
    );
    return List<String>.from(result.map((x) => x.toString()));
  }

  /// Fetch all seats registered in the database
  static Future<List<dynamic>> getAllSeats() async {
    final result = await _callDbWithCache(
      "cache_all_seats",
      "get_all_seats",
    );
    return List<dynamic>.from(result);
  }

  /// Fetch layout size (rows, columns, spacing) for a specific room
  static Future<Map<String, int>> getRoomLayout(String room) async {
    final result = await _callDbWithCache(
      "cache_room_layout_$room",
      "get_room_layout",
      args: [room],
    );
    // Returns List: [rows, columns, seat_spacing]
    if (result is List && result.length >= 3) {
      return {
        "rows": int.parse(result[0].toString()),
        "columns": int.parse(result[1].toString()),
        "spacing": int.parse(result[2].toString()),
      };
    }
    return {"rows": 5, "columns": 5, "spacing": 8};
  }

  /// Fetch student photo_path from database
  static Future<String?> getStudentPhotoPath(int studentId) async {
    final result = await _callDbWithCache(
      "cache_photo_path_$studentId",
      "get_student_photo_path",
      args: [studentId],
    );
    return result?.toString();
  }

  // ==========================================
  // MUTATION METHODS (Restricted in Offline Mode to prevent multi-device conflicts)
  // ==========================================

  /// Record payment logs to cloud database
  static Future<Map<String, dynamic>> recordPayment(
    int studentId,
    double amount,
    String paymentDate,
    String notes,
  ) async {
    if (!isOnline.value) {
      return {
        "success": false,
        "message": "Offline Mode: Recording payments is restricted while offline to prevent ledger discrepancies across devices. Please connect to the internet."
      };
    }
    final result = await _callDb(
      "record_payment",
      args: [studentId, amount, paymentDate, notes],
    );
    return {
      "success": result[0],
      "message": result[1],
    };
  }

  /// Record advance payment for multiple months
  static Future<Map<String, dynamic>> recordAdvancePayment(
    int studentId,
    int numMonths,
    String paymentDate,
    String notes,
  ) async {
    if (!isOnline.value) {
      return {
        "success": false,
        "message": "Offline Mode: Recording advance payments is restricted while offline. Please connect to the internet."
      };
    }
    final result = await _callDb(
      "record_advance_payment",
      args: [studentId, numMonths, paymentDate, notes],
    );
    return {
      "success": result[0],
      "message": result[1],
    };
  }

  /// Mark notice as sent (updates sent_at timestamp)
  static Future<void> markNoticeSent(int noticeId) async {
    if (!isOnline.value) return; // Silent skip if offline
    try {
      await _callDb("mark_notice_sent", args: [noticeId]);
    } catch (_) {}
  }

  /// Update general notice template settings
  static Future<void> setGeneralNoticeTemplate(String template) async {
    if (!isOnline.value) {
      throw Exception("Offline Mode: Updating notice templates requires an internet connection.");
    }
    await _callDb("set_general_notice_template", args: [template]);
  }

  /// Update a student's monthly fee and optionally their due amount
  static Future<void> updateMonthlyFee(int studentId, double monthlyFee, {double? newDue}) async {
    if (!isOnline.value) {
      throw Exception("Offline Mode: Fee modifications are restricted while offline.");
    }
    if (newDue != null) {
      await _callDb("update_monthly_fee", args: [studentId, monthlyFee, newDue]);
    } else {
      await _callDb("update_monthly_fee", args: [studentId, monthlyFee]);
    }
  }

  /// Trigger server-side fee notice generation (safe to call repeatedly)
  static Future<void> generateFeeNotices() async {
    if (!isOnline.value) return; // Skip if offline
    try {
      await _callDb("generate_fee_notices");
    } catch (_) {}
  }

  /// Create a new student profile in the database
  static Future<Map<String, dynamic>> addStudent({
    required String seatNumber,
    required String fullName,
    required String mobileNumber,
    required String admissionDate,
    required double monthlyFee,
    required String shiftType,
  }) async {
    if (!isOnline.value) {
      return {
        "success": false,
        "message": "Offline Mode: Adding new admissions is restricted while offline to prevent duplicate seat allocations across devices. Please connect to the internet."
      };
    }
    final result = await _callDb(
      "add_student",
      args: [seatNumber, fullName, mobileNumber, admissionDate, monthlyFee, shiftType],
    );
    if (result is int) {
      return {"success": true, "student_id": result};
    } else if (result is List && result.isNotEmpty && result[0] == false) {
      return {"success": false, "message": result[1]};
    }
    return {"success": false, "message": "Unexpected response from server: $result"};
  }

  /// Update an existing student profile in the database
  static Future<Map<String, dynamic>> updateStudent({
    required int studentId,
    required String fullName,
    required String mobileNumber,
    required String admissionDate,
    required double monthlyFee,
    required String shiftType,
  }) async {
    if (!isOnline.value) {
      return {
        "success": false,
        "message": "Offline Mode: Updating student profiles is restricted while offline to prevent data overwrite conflicts. Please connect to the internet."
      };
    }
    final result = await _callDb(
      "update_student",
      args: [studentId, fullName, mobileNumber, admissionDate, monthlyFee, shiftType],
    );
    if (result is List && result.length >= 2) {
      return {
        "success": result[0],
        "message": result[1],
      };
    }
    return {"success": false, "message": "Unexpected response from server: $result"};
  }

  /// Mark a student as an old student (exit)
  static Future<bool> markOldStudent(int studentId, String exitDate) async {
    if (!isOnline.value) {
      throw Exception("Offline Mode: Exiting students is restricted while offline to prevent multi-device seat conflicts.");
    }
    final result = await _callDb("mark_old_student", args: [studentId, exitDate]);
    return result == true;
  }

  // ==========================================
  // PHOTO HELPERS
  // ==========================================

  /// Build the URL where a student's photo is served
  static String? getStudentPhotoUrl(String? photoPath) {
    if (photoPath == null || photoPath.isEmpty) return null;
    final filename = photoPath.split('/').last.split('\\').last;
    if (filename.isEmpty) return null;
    return "$baseUrl/student_photos/$filename";
  }

  /// Build the URL for student photo thumbnail
  static String? getStudentThumbUrl(String? photoPath) {
    if (photoPath == null || photoPath.isEmpty) return null;
    final filename = photoPath.split('/').last.split('\\').last;
    if (filename.isEmpty) return null;
    final dotIdx = filename.lastIndexOf('.');
    if (dotIdx < 0) return "$baseUrl/student_photos/$filename";
    final stem = filename.substring(0, dotIdx);
    final ext = filename.substring(dotIdx);
    return "$baseUrl/student_photos/${stem}_thumb$ext";
  }

  /// Upload a photo file for a student via multipart POST
  static Future<Map<String, dynamic>> uploadStudentPhoto(int studentId, XFile photoFile) async {
    if (!isOnline.value) {
      throw Exception("Offline Mode: Photo upload requires an active internet connection.");
    }
    final uri = Uri.parse("$baseUrl/api/student-photo/upload");

    final request = http.MultipartRequest('POST', uri);
    request.headers['X-API-Key'] = apiKey;
    request.fields['student_id'] = studentId.toString();

    final bytes = await photoFile.readAsBytes();
    request.files.add(
      http.MultipartFile.fromBytes(
        'photo',
        bytes,
        filename: photoFile.name,
      ),
    );

    try {
      final streamedResponse = await request.send().timeout(const Duration(seconds: 30));
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode != 200) {
        final body = jsonDecode(response.body);
        throw Exception(body['error'] ?? 'Upload failed (${response.statusCode})');
      }

      return Map<String, dynamic>.from(jsonDecode(response.body));
    } catch (e) {
      throw Exception("Photo upload failed: $e");
    }
  }
}
