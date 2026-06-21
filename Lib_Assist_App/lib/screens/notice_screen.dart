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
  static const _smsChannel = MethodChannel('com.example.lib_assist/sms');

  bool _isLoading = true;
  String? _errorMessage;
  List<dynamic> _notices = [];
  String _currentFilter = "Pending"; // Pending | Due | Overdue | Reminder Due | All

  // Bulk Send Wizard state
  bool _inBulkWizard = false;
  int _bulkWizardIndex = 0;
  List<dynamic> _bulkNotices = [];
  String _bulkWizardChannel = "WhatsApp"; // "WhatsApp" | "SMS"
  bool _isAutoSendingSMS = false;

  @override
  void initState() {
    super.initState();
    _loadNotices();
  }

  void _startBulkWizard() {
    final unsent = _notices.where((n) => n['sent_at'] == null).toList();
    if (unsent.isEmpty) {
      if (_notices.isEmpty) {
        _showSnackbar("No notices available in this tab.", AppColors.warning);
        return;
      }
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Resend Notices?'),
          content: Text('All notices in the "${_currentFilter}" tab have already been marked as sent. Do you want to restart the wizard to send them again?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(ctx);
                _launchWizardWithNotices(_notices);
              },
              style: ElevatedButton.styleFrom(backgroundColor: AppColors.accent, foregroundColor: Colors.white),
              child: const Text('Yes, Resend All'),
            ),
          ],
        ),
      );
      return;
    }
    _launchWizardWithNotices(unsent);
  }

  void _launchWizardWithNotices(List<dynamic> targets) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('🚀 Choose Bulk Method'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Select how you want to send bulk notices for "${_currentFilter}" (${targets.length} total):'),
            const SizedBox(height: 8),
          ],
        ),
        actions: [
          ElevatedButton.icon(
            onPressed: () {
              Navigator.pop(ctx);
              setState(() {
                _bulkWizardChannel = "WhatsApp";
                _bulkNotices = targets;
                _bulkWizardIndex = 0;
                _inBulkWizard = true;
                _isAutoSendingSMS = false;
              });
            },
            icon: const Icon(Icons.chat_bubble_rounded),
            label: const Text('WhatsApp'),
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF25D366), foregroundColor: Colors.white),
          ),
          ElevatedButton.icon(
            onPressed: () {
              Navigator.pop(ctx);
              setState(() {
                _bulkWizardChannel = "SMS";
                _bulkNotices = targets;
                _bulkWizardIndex = 0;
                _inBulkWizard = true;
                _isAutoSendingSMS = false;
              });
            },
            icon: const Icon(Icons.sms_rounded),
            label: const Text('Auto SMS (Hands-free)'),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.accent, foregroundColor: Colors.white),
          ),
        ],
      ),
    );
  }

  void _exitBulkWizard() {
    setState(() {
      _inBulkWizard = false;
    });
    _loadNotices();
  }

  Future<void> _bulkSendCurrent() async {
    if (_bulkWizardIndex >= _bulkNotices.length) return;
    final notice = _bulkNotices[_bulkWizardIndex];
    final phone = notice['mobile_number'] ?? '';
    final message = notice['message'] ?? '';
    final noticeId = notice['id'];

    if (phone.isEmpty) {
      _showSnackbar("No mobile number configured for this student.", AppColors.danger);
      return;
    }

    String cleanPhone = phone.replaceAll(RegExp(r'\D'), '');
    if (cleanPhone.length == 10) {
      cleanPhone = '91$cleanPhone';
    }

    if (_bulkWizardChannel == "SMS") {
      try {
        await _smsChannel.invokeMethod('sendSMS', {
          'phone': cleanPhone,
          'message': message,
        });
        await ApiService.markNoticeSent(noticeId);
        _showSnackbar("SMS sent successfully to ${notice['full_name']}! ✉️", AppColors.success);
      } catch (e) {
        _showErrorDialog(
          "Failed to send SMS to ${notice['full_name']} ($phone):\n\n$e\n\n"
          "Please verify:\n"
          "1. SMS permissions are granted in phone Settings -> Apps.\n"
          "2. Device has a working SIM card with SMS pack balance."
        );
        return; // Halt and wait for user correction/skip
      }

      setState(() {
        if (_bulkWizardIndex < _bulkNotices.length - 1) {
          _bulkWizardIndex++;
        } else {
          _inBulkWizard = false;
          _showSnackbar("Bulk SMS sending completed successfully! 🎉", AppColors.success);
          _loadNotices();
        }
      });
      return;
    }

    final String urlStr = "https://wa.me/$cleanPhone?text=${Uri.encodeComponent(message)}";
    final Uri url = Uri.parse(urlStr);

    try {
      if (await canLaunchUrl(url)) {
        await launchUrl(url, mode: LaunchMode.externalApplication);
      } else {
        _showSnackbar("Could not open WhatsApp app directly.", AppColors.warning);
      }
    } catch (e) {
      _showSnackbar("Could not open WhatsApp app.", AppColors.warning);
    }

    try {
      await ApiService.markNoticeSent(noticeId);
    } catch (e) {
      // Ignore background write errors to allow wizard progression
    }

    _showSnackbar("Sent notice to ${notice['full_name']}!", AppColors.success);

    setState(() {
      if (_bulkWizardIndex < _bulkNotices.length - 1) {
        _bulkWizardIndex++;
      } else {
        _inBulkWizard = false;
        _showSnackbar("Bulk sending completed successfully! 🎉", AppColors.success);
        _loadNotices();
      }
    });
  }

  Future<void> _startAutoSMSLoop() async {
    setState(() {
      _isAutoSendingSMS = true;
    });

    while (_isAutoSendingSMS && _bulkWizardIndex < _bulkNotices.length) {
      final notice = _bulkNotices[_bulkWizardIndex];
      final phone = notice['mobile_number'] ?? '';
      final message = notice['message'] ?? '';
      final noticeId = notice['id'];

      if (phone.isEmpty) {
        _stopAutoSMSLoop();
        _showErrorDialog("Failed to send notice to ${notice['full_name']}: Mobile number is empty.");
        break;
      }

      String cleanPhone = phone.replaceAll(RegExp(r'\D'), '');
      if (cleanPhone.length == 10) {
        cleanPhone = '91$cleanPhone';
      }

      try {
        await _smsChannel.invokeMethod('sendSMS', {
          'phone': cleanPhone,
          'message': message,
        });
        await ApiService.markNoticeSent(noticeId);
      } catch (e) {
        _stopAutoSMSLoop();
        _showErrorDialog(
          "Failed to send SMS to ${notice['full_name']} ($phone):\n\n$e\n\n"
          "Please verify:\n"
          "1. SMS permissions are granted in phone Settings -> Apps.\n"
          "2. Device has a working SIM card with SMS pack balance."
        );
        break; // Stop loop immediately on error
      }

      await Future.delayed(const Duration(milliseconds: 1500));

      if (!_isAutoSendingSMS) break;

      setState(() {
        if (_bulkWizardIndex < _bulkNotices.length - 1) {
          _bulkWizardIndex++;
        } else {
          _inBulkWizard = false;
          _isAutoSendingSMS = false;
          _showSnackbar("Automated Bulk SMS sending completed! 🎉", AppColors.success);
          _loadNotices();
        }
      });
    }
  }

  void _stopAutoSMSLoop() {
    setState(() {
      _isAutoSendingSMS = false;
    });
  }

  void _bulkSkipCurrent() {
    setState(() {
      if (_bulkWizardIndex < _bulkNotices.length - 1) {
        _bulkWizardIndex++;
      } else {
        _inBulkWizard = false;
        _showSnackbar("Bulk sending completed! 🎉", AppColors.success);
        _loadNotices();
      }
    });
  }

  void _bulkPrevCurrent() {
    if (_bulkWizardIndex > 0) {
      setState(() {
        _bulkWizardIndex--;
      });
    }
  }

  Widget _buildBulkWizardView() {
    if (_bulkNotices.isEmpty || _bulkWizardIndex >= _bulkNotices.length) {
      return const Center(child: Text("No notices to process."));
    }

    final notice = _bulkNotices[_bulkWizardIndex];
    final String name = notice['full_name'] ?? '';
    final String seat = notice['seat_number'] ?? '';
    final String phone = notice['mobile_number'] ?? '';
    final String message = notice['message'] ?? '';
    final double pct = (_bulkWizardIndex + 1) / _bulkNotices.length;

    return Container(
      color: AppColors.bg,
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '🤖 Bulk Send Wizard',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Send notices to all due students sequentially',
                    style: TextStyle(fontSize: 11, color: AppColors.textSecondary),
                  ),
                ],
              ),
              IconButton(
                icon: const Icon(Icons.close_rounded, color: AppColors.textSecondary),
                onPressed: _exitBulkWizard,
              ),
            ],
          ),
          const SizedBox(height: 20),
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              LinearProgressIndicator(
                value: pct,
                backgroundColor: AppColors.primary.withOpacity(0.1),
                color: AppColors.accent,
                minHeight: 6,
                borderRadius: BorderRadius.circular(3),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Text(
                        'Notice ${_bulkWizardIndex + 1} of ${_bulkNotices.length}',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textSecondary),
                      ),
                      if (_isAutoSendingSMS) ...[
                        const SizedBox(width: 8),
                        const SizedBox(
                          width: 12,
                          height: 12,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(AppColors.accent),
                          ),
                        ),
                      ],
                    ],
                  ),
                  Text(
                    '${(pct * 100).toStringAsFixed(0)}% Complete',
                    style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 24),
          Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Row(
                children: [
                  Container(
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(
                      color: AppColors.accent.withOpacity(0.1),
                      shape: BoxShape.circle,
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      (name.isNotEmpty ? name[0] : '?').toUpperCase(),
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: AppColors.accent),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          name,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.textPrimary),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Seat: $seat | Phone: $phone',
                          style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.cardBg,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'MESSAGE TEMPLATE',
                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppColors.textSecondary, letterSpacing: 1.1),
                  ),
                  const SizedBox(height: 10),
                  Expanded(
                    child: SingleChildScrollView(
                      child: Text(
                        message,
                        style: const TextStyle(fontSize: 14, height: 1.5, color: AppColors.textPrimary),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: (_isAutoSendingSMS || _bulkWizardIndex == 0) ? null : _bulkPrevCurrent,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.primary,
                    side: const BorderSide(color: AppColors.primary),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  child: const Text('⬅ Prev', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton(
                  onPressed: _isAutoSendingSMS ? null : _bulkSkipCurrent,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.textSecondary,
                    side: const BorderSide(color: AppColors.border),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  child: Text(
                    _bulkWizardIndex == _bulkNotices.length - 1 ? 'Skip & Done ✓' : 'Skip / Next ➔',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_bulkWizardChannel == "SMS") ...[
            if (_isAutoSendingSMS)
              ElevatedButton.icon(
                onPressed: _stopAutoSMSLoop,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.danger,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(vertical: 15),
                  elevation: 0,
                ),
                icon: const Icon(Icons.pause_circle_filled_rounded),
                label: const Text(
                  '🛑 Pause Auto-Send',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              )
            else ...[
              ElevatedButton.icon(
                onPressed: _startAutoSMSLoop,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.accent,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(vertical: 15),
                  elevation: 0,
                ),
                icon: const Icon(Icons.play_circle_filled_rounded),
                label: const Text(
                  '▶ Auto-Send All (SMS)',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: _bulkSendCurrent,
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.primary,
                  side: const BorderSide(color: AppColors.primary),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                icon: const Icon(Icons.send_rounded, size: 18),
                label: const Text(
                  'Send & Next (Manual SMS)',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ] else ...[
            ElevatedButton.icon(
              onPressed: _bulkSendCurrent,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF25D366),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                padding: const EdgeInsets.symmetric(vertical: 15),
                elevation: 0,
              ),
              icon: const Icon(Icons.chat_bubble_rounded),
              label: const Text(
                'Send & Next',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ],
      ),
    );
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
    if (cleanPhone.length == 10) {
      cleanPhone = '91$cleanPhone';
    }

    // Try native background SMS sending first (Android only)
    try {
      await _smsChannel.invokeMethod('sendSMS', {
        'phone': cleanPhone,
        'message': message,
      });
      await _promptMarkSent(noticeId);
      _showSnackbar("SMS sent in background successfully! ✉️", AppColors.success);
      return;
    } catch (e) {
      debugPrint("Background SMS failed, falling back to composer: $e");
    }

    // Fallback: system SMS composer
    final Uri smsUri = Uri.parse('sms:$cleanPhone?body=${Uri.encodeComponent(message)}');

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

  void _showErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.error_outline_rounded, color: AppColors.danger),
            SizedBox(width: 8),
            Text('SMS Sending Failed'),
          ],
        ),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final hasUnsentNotices = _notices.any((n) => n['sent_at'] == null);
    return Scaffold(
      appBar: AppBar(
        title: const Text('🔔 Notice Center'),
        actions: [
          if (!_inBulkWizard)
            TextButton.icon(
              icon: const Icon(Icons.edit_note_rounded, color: Colors.white, size: 20),
              label: const Text('Gen_Msg', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
              onPressed: _showGenMsgDialog,
            ),
          if (!_isLoading && _errorMessage == null && _notices.isNotEmpty && !_inBulkWizard)
            IconButton(
              icon: const Icon(Icons.rocket_launch_outlined),
              tooltip: 'Bulk Send Wizard',
              onPressed: _startBulkWizard,
            ),
        ],
      ),
      body: _inBulkWizard
          ? _buildBulkWizardView()
          : Column(
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

  Future<void> _showGenMsgDialog() async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) {
        return _GenMsgDialogContent(
          onSaved: () {
            _loadNotices();
          },
        );
      },
    );
  }
}

class _GenMsgDialogContent extends StatefulWidget {
  final VoidCallback onSaved;
  const _GenMsgDialogContent({required this.onSaved});

  @override
  State<_GenMsgDialogContent> createState() => _GenMsgDialogContentState();
}

class _GenMsgDialogContentState extends State<_GenMsgDialogContent> {
  final TextEditingController _controller = TextEditingController();
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchTemplate();
  }

  Future<void> _fetchTemplate() async {
    try {
      final template = await ApiService.getGeneralNoticeTemplate();
      setState(() {
        _controller.text = template;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _saveTemplate() async {
    final text = _controller.text;
    if (text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Template cannot be empty')),
      );
      return;
    }
    setState(() {
      _saving = true;
    });
    try {
      await ApiService.setGeneralNoticeTemplate(text);
      if (mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('General message template updated!'),
            backgroundColor: AppColors.success,
          ),
        );
        widget.onSaved();
      }
    } catch (e) {
      setState(() {
        _saving = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to save template: $e'), backgroundColor: AppColors.danger),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('📝 Edit General Notice'),
      content: _loading
          ? const SizedBox(
              height: 100,
              child: Center(child: CircularProgressIndicator(color: AppColors.accent)),
            )
          : SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'Customize the general notice template. Use the placeholders below to insert values dynamically:',
                    style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.bg,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: const Text(
                      '• <std_name>  ->  Student\'s Name\n• <Date>  ->  Due Date',
                      style: TextStyle(fontFamily: 'monospace', fontSize: 12, color: AppColors.textPrimary, height: 1.4),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _controller,
                    maxLines: 6,
                    decoration: const InputDecoration(
                      labelText: 'General Notice Template',
                      alignLabelWithHint: true,
                      border: OutlineInputBorder(),
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 8),
                    Text(_error!, style: const TextStyle(color: AppColors.danger, fontSize: 12)),
                  ],
                ],
              ),
            ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.pop(context),
          child: const Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
        ),
        if (!_loading)
          ElevatedButton(
            onPressed: _saving ? null : _saveTemplate,
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.accent,
              foregroundColor: Colors.white,
            ),
            child: _saving
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                  )
                : const Text('Save'),
          ),
      ],
    );
  }
}
