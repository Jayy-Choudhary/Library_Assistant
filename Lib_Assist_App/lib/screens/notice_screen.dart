import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import '../theme/colors.dart';
import '../services/api_service.dart';

class NoticeScreen extends StatefulWidget {
  const NoticeScreen({super.key});

  @override
  State<NoticeScreen> createState() => _NoticeScreenState();
}

class _NoticeScreenState extends State<NoticeScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  List<dynamic> _notices = [];
  String _currentFilter = "Pending"; // Pending | Due | Overdue | Reminder Due | All

  @override
  void initState() {
    super.initState();
    _loadNotices();
  }

  Future<void> _loadNotices() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final data = await ApiService.getNoticeCenterRows(_currentFilter);
      setState(() {
        _notices = data;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _sendWhatsApp(Map<String, dynamic> notice) async {
    final phone = notice['mobile_number'] ?? '';
    final message = notice['message'] ?? '';
    final noticeId = notice['id'];

    if (phone.isEmpty) {
      _showSnackbar("No mobile number configured for this student.", AppColors.danger);
      return;
    }

    // Clean phone number and prepend country code (91 for India) if needed
    String cleanPhone = phone.replaceAll(RegExp(r'\D'), '');
    if (cleanPhone.length == 10) {
      cleanPhone = '91$cleanPhone';
    }

    final String urlStr = "https://wa.me/$cleanPhone?text=${Uri.encodeComponent(message)}";
    final Uri url = Uri.parse(urlStr);

    try {
      if (await canLaunchUrl(url)) {
        await launchUrl(url, mode: LaunchMode.externalApplication);
        await _promptMarkSent(noticeId);
      } else {
        throw Exception("Could not launch WhatsApp app.");
      }
    } catch (e) {
      _showFallbackActionDialog(noticeId, phone, message, "WhatsApp");
    }
  }

  Future<void> _sendSMS(Map<String, dynamic> notice) async {
    final phone = notice['mobile_number'] ?? '';
    final message = notice['message'] ?? '';
    final noticeId = notice['id'];

    if (phone.isEmpty) {
      _showSnackbar("No mobile number configured for this student.", AppColors.danger);
      return;
    }

    String cleanPhone = phone.replaceAll(RegExp(r'\D'), '');
    final Uri smsUri = Uri(
      scheme: 'sms',
      path: cleanPhone,
      queryParameters: {'body': message},
    );

    try {
      if (await canLaunchUrl(smsUri)) {
        await launchUrl(smsUri);
        await _promptMarkSent(noticeId);
      } else {
        throw Exception("Could not launch SMS app.");
      }
    } catch (e) {
      _showFallbackActionDialog(noticeId, phone, message, "SMS");
    }
  }

  Future<void> _promptMarkSent(int noticeId) async {
    // Automatically trigger markSent backend call since user chose to send
    try {
      await ApiService.markNoticeSent(noticeId);
      _showSnackbar("Notice marked as sent!", AppColors.success);
      _loadNotices();
    } catch (e) {
      _showSnackbar("Notice initiated, but failed to update status on server.", AppColors.warning);
    }
  }

  void _showFallbackActionDialog(int noticeId, String phone, String message, String channel) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Could not open $channel'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("We couldn't automatically open your $channel app. You can copy the message and send it manually."),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.bg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.textSecondary.withOpacity(0.3)),
              ),
              child: Text(
                message,
                maxLines: 4,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 13, fontStyle: FontStyle.italic),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
          ),
          TextButton(
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: message));
              Navigator.pop(ctx);
              _showSnackbar("Message copied to clipboard!", AppColors.success);
              // Ask if they want to mark as sent anyway
              _showMarkSentConfirmation(noticeId);
            },
            child: const Text('Copy Message'),
          ),
        ],
      ),
    );
  }

  void _showMarkSentConfirmation(int noticeId) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Mark Notice Sent?'),
        content: const Text('Since you copied the message to send manually, would you like to mark this notice as sent in the database?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('No'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await _promptMarkSent(noticeId);
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.accent,
              foregroundColor: Colors.white,
            ),
            child: const Text('Yes, Mark Sent'),
          ),
        ],
      ),
    );
  }

  void _showSnackbar(String msg, Color bgColor) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: bgColor,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('🔔 Notice Center'),
      ),
      body: Column(
        children: [
          _buildFilterBar(),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: AppColors.accent))
                : _errorMessage != null
                    ? _buildErrorView()
                    : _notices.isEmpty
                        ? _buildEmptyView()
                        : RefreshIndicator(
                            onRefresh: _loadNotices,
                            child: ListView.builder(
                              itemCount: _notices.length,
                              itemBuilder: (context, idx) {
                                final notice = _notices[idx];
                                return _buildNoticeCard(notice);
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterBar() {
    final filters = ["Pending", "Due", "Overdue", "Reminder Due", "All"];
    return Container(
      color: AppColors.primary,
      height: 60,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        itemCount: filters.length,
        itemBuilder: (context, index) {
          final filter = filters[index];
          final isSelected = _currentFilter == filter;
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4.0),
            child: ChoiceChip(
              label: Text(
                filter,
                style: TextStyle(
                  color: isSelected ? Colors.white : AppColors.textSecondary,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                ),
              ),
              selected: isSelected,
              selectedColor: AppColors.accent,
              backgroundColor: AppColors.primary.withAlpha(50),
              checkmarkColor: Colors.white,
              side: BorderSide.none,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              onSelected: (selected) {
                if (selected) {
                  setState(() {
                    _currentFilter = filter;
                  });
                  _loadNotices();
                }
              },
            ),
          );
        },
      ),
    );
  }

  Widget _buildNoticeCard(Map<String, dynamic> notice) {
    final isSent = notice['sent_at'] != null;
    final sentAtStr = notice['sent_at'] ?? '';
    final double dueAmount = double.parse((notice['due_amount'] ?? 0).toString());
    final status = notice['status'] ?? 'Pending';

    // Status styling
    Color statusColor;
    switch (status) {
      case 'Paid':
        statusColor = AppColors.success;
        break;
      case 'Cancelled':
        statusColor = AppColors.textSecondary;
        break;
      default:
        statusColor = AppColors.warning;
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: Student Name + Seat
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        notice['full_name'] ?? '',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.textPrimary),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Seat ${notice['seat_number'] ?? '-'} • Due: ₹${dueAmount.toStringAsFixed(0)}',
                        style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    status,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: statusColor,
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: 20),

            // Message template text block
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.bg,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.textSecondary.withOpacity(0.15)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'MESSAGE TEMPLATE',
                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppColors.textSecondary, letterSpacing: 1.1),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    notice['message'] ?? '',
                    style: const TextStyle(fontSize: 13, height: 1.4, color: AppColors.textPrimary),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Sent Timestamp Info
            Row(
              children: [
                Icon(
                  isSent ? Icons.check_circle_outline_rounded : Icons.info_outline_rounded,
                  size: 16,
                  color: isSent ? AppColors.success : AppColors.warning,
                ),
                const SizedBox(width: 4),
                Text(
                  isSent ? 'Sent: $sentAtStr' : 'Not sent to student yet',
                  style: TextStyle(
                    fontSize: 12,
                    color: isSent ? AppColors.success : AppColors.textSecondary,
                    fontWeight: isSent ? FontWeight.bold : FontWeight.normal,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Action row buttons
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _sendSMS(notice),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.primary,
                      side: const BorderSide(color: AppColors.primary),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    icon: const Icon(Icons.sms_rounded, size: 18),
                    label: const Text('Send SMS', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => _sendWhatsApp(notice),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF25D366), // Official WhatsApp brand green
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    icon: const Icon(Icons.chat_bubble_rounded, size: 18),
                    label: const Text('WhatsApp', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyView() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.mark_email_read_outlined, color: AppColors.textSecondary, size: 64),
          SizedBox(height: 16),
          Text(
            'No notices match current filter',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorView() {
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline_rounded, color: AppColors.danger, size: 64),
            const SizedBox(height: 16),
            const Text(
              'Error loading notices',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
            ),
            const SizedBox(height: 8),
            Text(
              _errorMessage ?? 'Unknown error',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _loadNotices,
              style: ElevatedButton.styleFrom(backgroundColor: AppColors.accent, foregroundColor: Colors.white),
              child: const Text('Reload'),
            ),
          ],
        ),
      ),
    );
  }
}
