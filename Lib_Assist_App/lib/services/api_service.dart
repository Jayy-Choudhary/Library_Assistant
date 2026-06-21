import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  // Default connection details matching your PythonAnywhere server config
  static String baseUrl = "https://jaychoudhary.pythonanywhere.com";
  static String apiKey = "jay-library-secret-key-2026";

  /// Initialize and load saved connection settings from SharedPreferences
  static Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    baseUrl = prefs.getString('api_base_url') ?? "https://jaychoudhary.pythonanywhere.com";
    apiKey = prefs.getString('api_key') ?? "jay-library-secret-key-2026";
  }

  /// Update server connection configuration
  static Future<void> updateConnectionSettings(String newUrl, String newKey) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('api_base_url', newUrl);
    await prefs.setString('api_key', newKey);
    baseUrl = newUrl;
    apiKey = newKey;
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
    } catch (e) {
      return false;
    }
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
      
      return data["result"];
    } catch (e) {
      throw Exception("API Connection Failed: $e");
    }
  }

  /// Fetch dashboard counters and lists in 1 batch request
  static Future<Map<String, dynamic>> getDashboardMetrics() async {
    final result = await _callDb("get_dashboard_metrics");
    return Map<String, dynamic>.from(result);
  }

  /// List active/old students from database
  static Future<List<dynamic>> getStudents({String filter = "Active"}) async {
    final args = filter == "All" ? [] : [filter];
    final result = await _callDb("get_all_students", args: args);
    return List<dynamic>.from(result);
  }

  /// Search students by query string
  static Future<List<dynamic>> searchStudents(String query) async {
    final result = await _callDb("search_students", args: [query]);
    return List<dynamic>.from(result);
  }

  /// Fetch detail profile for student
  static Future<Map<String, dynamic>?> getStudentById(int studentId) async {
    final result = await _callDb("get_student_by_id", args: [studentId]);
    return result != null ? Map<String, dynamic>.from(result) : null;
  }

  /// Fetch specific student fee record details
  static Future<Map<String, dynamic>?> getFeeRecord(int studentId) async {
    final result = await _callDb("get_fee_record", args: [studentId]);
    return result != null ? Map<String, dynamic>.from(result) : null;
  }

  /// Fetch payment logs for a student
  static Future<List<dynamic>> getPaymentHistory(int studentId) async {
    final result = await _callDb("get_payment_history", args: [studentId]);
    return List<dynamic>.from(result);
  }

  /// Record payment logs to cloud database
  static Future<Map<String, dynamic>> recordPayment(
    int studentId,
    double amount,
    String paymentDate,
    String notes,
  ) async {
    final result = await _callDb(
      "record_payment",
      args: [studentId, amount, paymentDate, notes],
    );
    // Returns List: [successBool, message]
    return {
      "success": result[0],
      "message": result[1],
    };
  }

  /// Fetch notices filtered by state (Pending, Due, Overdue, Reminder Due)
  static Future<List<dynamic>> getNoticeCenterRows(String filter) async {
    final result = await _callDb("get_notice_center_rows", args: [filter]);
    return List<dynamic>.from(result);
  }

  /// Mark notice as sent (updates sent_at timestamp)
  static Future<void> markNoticeSent(int noticeId) async {
    await _callDb("mark_notice_sent", args: [noticeId]);
  }

  /// Fetch seats compatible with a target shift type
  static Future<List<String>> getCompatibleSeats(String shiftType) async {
    final result = await _callDb("get_compatible_seats", args: [shiftType]);
    return List<String>.from(result.map((x) => x.toString()));
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
    final result = await _callDb(
      "add_student",
      args: [seatNumber, fullName, mobileNumber, admissionDate, monthlyFee, shiftType],
    );
    // Returns student_id (int) or [false, error_msg]
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
    final result = await _callDb(
      "update_student",
      args: [studentId, fullName, mobileNumber, admissionDate, monthlyFee, shiftType],
    );
    // Returns [successBool, message]
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
    final result = await _callDb("mark_old_student", args: [studentId, exitDate]);
    return result == true;
  }
}

