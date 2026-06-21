import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../theme/colors.dart';
import '../services/api_service.dart';
import 'student_form_screen.dart';


class StudentDetailScreen extends StatefulWidget {
  final int studentId;

  const StudentDetailScreen({
    super.key,
    required this.studentId,
  });

  @override
  State<StudentDetailScreen> createState() => _StudentDetailScreenState();
}

class _StudentDetailScreenState extends State<StudentDetailScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  Map<String, dynamic>? _student;
  Map<String, dynamic>? _feeRecord;
  List<dynamic> _paymentHistory = [];
  bool _isSavingPayment = false;
  bool _anyChangesSaved = false;


  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final studentData = await ApiService.getStudentById(widget.studentId);
      if (studentData == null) {
        throw Exception("Student not found in database.");
      }

      final feeData = await ApiService.getFeeRecord(widget.studentId);
      final historyData = await ApiService.getPaymentHistory(widget.studentId);

      setState(() {
        _student = studentData;
        _feeRecord = feeData;
        _paymentHistory = historyData;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(color: AppColors.accent),
        ),
      );
    }

    if (_errorMessage != null || _student == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Student Profile')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline_rounded, color: AppColors.danger, size: 64),
                const SizedBox(height: 16),
                Text(
                  _errorMessage ?? 'Failed to load details',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: _loadData,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    foregroundColor: Colors.white,
                  ),
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final student = _student!;
    final bool isActive = student['status'] == 'Active';
    final photoPath = student['photo_path']?.toString();
    final photoUrl = ApiService.getStudentPhotoUrl(photoPath);

    final double dueAmount = _feeRecord != null ? double.parse((_feeRecord!['due_amount'] ?? 0).toString()) : 0.0;
    final double monthlyFee = _feeRecord != null ? double.parse((_feeRecord!['monthly_fee'] ?? 0).toString()) : 0.0;

    return PopScope(
      canPop: true,
      onPopInvoked: (didPop) {
        // Return changes status to parent screen to refresh list
      },

      child: Scaffold(
        body: CustomScrollView(
          slivers: [
            // Gorgeous Header Section
            SliverAppBar(
              expandedHeight: 250.0,
              pinned: true,
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              leading: IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => Navigator.pop(context, _anyChangesSaved),
              ),
              actions: [
                IconButton(
                  icon: const Icon(Icons.edit_rounded),
                  tooltip: 'Edit Profile',
                  onPressed: () async {
                    final result = await Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => StudentFormScreen(studentId: widget.studentId),
                      ),
                    );
                    if (result == true) {
                      setState(() {
                        _anyChangesSaved = true;
                      });
                      _loadData();
                    }
                  },
                ),
              ],
              flexibleSpace: FlexibleSpaceBar(
                background: Container(
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      colors: [AppColors.primary, Color(0xFF1E293B)],
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                    ),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const SizedBox(height: 50),
                      CircleAvatar(
                        radius: 50,
                        backgroundColor: Colors.white.withOpacity(0.1),
                        backgroundImage: photoUrl != null ? NetworkImage(photoUrl) : null,
                        child: photoUrl == null
                            ? Text(
                                student['full_name'] != null && (student['full_name'] as String).isNotEmpty
                                    ? (student['full_name'] as String).substring(0, 1).toUpperCase()
                                    : '?',
                                style: const TextStyle(
                                  fontSize: 40,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white,
                                ),
                              )
                            : null,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        student['full_name'] ?? '',
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                        decoration: BoxDecoration(
                          color: (isActive ? AppColors.success : AppColors.textSecondary).withOpacity(0.2),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: (isActive ? AppColors.success : AppColors.textSecondary).withOpacity(0.5),
                            width: 1,
                          ),
                        ),
                        child: Text(
                          student['status'] ?? 'Active',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: isActive ? AppColors.success : AppColors.textSecondary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

            // Content List
            SliverList(
              delegate: SliverChildListDelegate([
                _buildSeatAndShiftInfo(student),
                _buildFeeStatusCard(monthlyFee, dueAmount),
                _buildProfileDetailList(student),
                if (isActive) _buildMarkOldButton(context, student),
                _buildPaymentHistoryList(),
                const SizedBox(height: 100), // safe space for bottom payment button
              ]),
            ),
          ],
        ),
        bottomSheet: Container(
          color: AppColors.bg,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: SizedBox(
            width: double.infinity,
            height: 52,
            child: ElevatedButton.icon(
              onPressed: (isActive && dueAmount > 0)
                  ? () => _showRecordPaymentDialog(context, dueAmount)
                  : null,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.accent,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                disabledBackgroundColor: AppColors.textSecondary.withOpacity(0.12),
                disabledForegroundColor: AppColors.textSecondary.withOpacity(0.5),
              ),
              icon: const Icon(Icons.currency_rupee_rounded),
              label: Text(
                dueAmount > 0
                    ? 'Record Payment (₹${dueAmount.toStringAsFixed(0)})'
                    : 'No Dues Pending',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSeatAndShiftInfo(Map<String, dynamic> student) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Row(
        children: [
          Expanded(
            child: Card(
              margin: EdgeInsets.zero,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    const Icon(Icons.chair_rounded, color: AppColors.accent, size: 28),
                    const SizedBox(height: 8),
                    const Text('Seat Number', style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                    const SizedBox(height: 4),
                    Text(
                      student['seat_number'] ?? '-',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: AppColors.textPrimary),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Card(
              margin: EdgeInsets.zero,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    const Icon(Icons.access_time_filled_rounded, color: AppColors.warning, size: 28),
                    const SizedBox(height: 8),
                    const Text('Shift Type', style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                    const SizedBox(height: 4),
                    Text(
                      student['shift_type'] ?? 'FULL_DAY',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.textPrimary),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeeStatusCard(double monthlyFee, double dueAmount) {
    if (_feeRecord == null) return const SizedBox.shrink();

    final dueDateStr = _feeRecord!['due_date'];
    final nextDueDateStr = _feeRecord!['next_due_date'];
    final lastPaymentDate = _feeRecord!['last_payment_date'];

    return Card(
      margin: const EdgeInsets.all(16),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.receipt_long_rounded, color: AppColors.primary),
                const SizedBox(width: 8),
                const Text(
                  'Fee & Account Summary',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.textPrimary),
                ),
                const Spacer(),
                if (dueAmount > 0)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.danger.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Text(
                      'Dues Pending',
                      style: TextStyle(color: AppColors.danger, fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                  ),
              ],
            ),
            const Divider(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _buildFeeStatItem('Monthly Fee', '₹${monthlyFee.toStringAsFixed(0)}'),
                _buildFeeStatItem('Due Amount', '₹${dueAmount.toStringAsFixed(0)}', isDue: dueAmount > 0),
              ],
            ),
            const SizedBox(height: 16),
            if (dueDateStr != null)
              _buildDetailRow('Current Due Date', dueDateStr),
            if (nextDueDateStr != null)
              _buildDetailRow('Next Renewal Date', nextDueDateStr),
            if (lastPaymentDate != null)
              _buildDetailRow('Last Payment Date', lastPaymentDate),
          ],
        ),
      ),
    );
  }

  Widget _buildFeeStatItem(String label, String value, {bool isDue = false}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontWeight: FontWeight.w800,
            fontSize: 20,
            color: isDue ? AppColors.danger : AppColors.textPrimary,
          ),
        ),
      ],
    );
  }

  Widget _buildProfileDetailList(Map<String, dynamic> student) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.badge_rounded, color: AppColors.primary),
                const SizedBox(width: 8),
                Text(
                  'Profile Information',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.textPrimary),
                ),
              ],
            ),
            const Divider(height: 24),
            _buildDetailRow('Mobile Number', student['mobile_number'] ?? '-'),
            _buildDetailRow('Admission Date', student['admission_date'] ?? '-'),
            if (student['exit_date'] != null)
              _buildDetailRow('Exit Date', student['exit_date']),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 14)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.textPrimary, fontSize: 14)),
        ],
      ),
    );
  }

  Widget _buildPaymentHistoryList() {
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(left: 8.0, bottom: 8.0),
            child: Text(
              '💸 Payment History',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.textPrimary),
            ),
          ),
          if (_paymentHistory.isEmpty)
            Card(
              margin: EdgeInsets.zero,
              child: const Padding(
                padding: EdgeInsets.all(24.0),
                child: Center(
                  child: Text(
                    'No payment records found.',
                    style: TextStyle(color: AppColors.textSecondary),
                  ),
                ),
              ),
            )
          else
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _paymentHistory.length,
              itemBuilder: (context, idx) {
                final payment = _paymentHistory[idx];
                final double amt = double.parse((payment['amount'] ?? 0).toString());
                final dateStr = payment['payment_date'] ?? '';
                final notes = payment['notes'] ?? '';

                return Card(
                  margin: const EdgeInsets.symmetric(vertical: 6),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: AppColors.success.withOpacity(0.1),
                      child: const Icon(Icons.done_all_rounded, color: AppColors.success, size: 20),
                    ),
                    title: Text(
                      '₹${amt.toStringAsFixed(0)} Paid',
                      style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                    ),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: 2),
                        Text(dateStr, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                        if (notes.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            notes,
                            style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic, color: AppColors.textSecondary),
                          ),
                        ]
                      ],
                    ),
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  void _showRecordPaymentDialog(BuildContext context, double currentDue) {
    final formKey = GlobalKey<FormState>();
    final amountController = TextEditingController(text: currentDue.toStringAsFixed(0));
    final notesController = TextEditingController();
    String selectedDateStr = DateFormat('yyyy-MM-dd').format(DateTime.now());

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (stContext, setDialogState) {
            return AlertDialog(
              title: const Text('Record Fee Payment'),
              content: Form(
                key: formKey,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // Amount input
                      TextFormField(
                        controller: amountController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(
                          labelText: 'Payment Amount (₹)',
                          border: OutlineInputBorder(),
                          prefixIcon: Icon(Icons.currency_rupee_rounded),
                        ),
                        validator: (val) {
                          if (val == null || val.trim().isEmpty) {
                            return 'Please enter amount';
                          }
                          final d = double.tryParse(val);
                          if (d == null || d <= 0) {
                            return 'Enter a valid amount > 0';
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 16),

                      // Date selector picker
                      InkWell(
                        onTap: () async {
                          final initialDate = DateTime.tryParse(selectedDateStr) ?? DateTime.now();
                          final picked = await showDatePicker(
                            context: context,
                            initialDate: initialDate,
                            firstDate: DateTime(2020),
                            lastDate: DateTime(2030),
                          );
                          if (picked != null) {
                            setDialogState(() {
                              selectedDateStr = DateFormat('yyyy-MM-dd').format(picked);
                            });
                          }
                        },
                        child: InputDecorator(
                          decoration: const InputDecoration(
                            labelText: 'Payment Date',
                            border: OutlineInputBorder(),
                            prefixIcon: Icon(Icons.calendar_today_rounded),
                          ),
                          child: Text(
                            selectedDateStr,
                            style: const TextStyle(fontSize: 16),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Notes input
                      TextFormField(
                        controller: notesController,
                        maxLines: 2,
                        decoration: const InputDecoration(
                          labelText: 'Notes / Payment Mode',
                          hintText: 'e.g. Cash, UPI, GPay Ref#',
                          border: OutlineInputBorder(),
                          prefixIcon: Icon(Icons.edit_note_rounded),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: _isSavingPayment ? null : () => Navigator.pop(dialogContext),
                  child: const Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
                ),
                ElevatedButton(
                  onPressed: _isSavingPayment
                      ? null
                      : () async {
                          if (!formKey.currentState!.validate()) return;

                          setDialogState(() {
                            _isSavingPayment = true;
                          });

                          try {
                            final double amountVal = double.parse(amountController.text.trim());
                            final result = await ApiService.recordPayment(
                              widget.studentId,
                              amountVal,
                              selectedDateStr,
                              notesController.text.trim(),
                            );

                            if (result['success'] == true) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(result['message'] ?? 'Payment recorded successfully!'),
                                  backgroundColor: AppColors.success,
                                ),
                              );
                              Navigator.pop(dialogContext);
                              setState(() {
                                _anyChangesSaved = true;
                              });
                              _loadData(); // reload details
                            } else {
                              throw Exception(result['message'] ?? 'Failed to record payment');
                            }
                          } catch (err) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('Error: ${err.toString()}'),
                                backgroundColor: AppColors.danger,
                              ),
                            );
                          } finally {
                            setDialogState(() {
                              _isSavingPayment = false;
                            });
                          }
                        },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    foregroundColor: Colors.white,
                  ),
                  child: _isSavingPayment
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : const Text('Submit Payment'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Widget _buildMarkOldButton(BuildContext context, Map<String, dynamic> student) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Card(
        color: AppColors.danger.withOpacity(0.05),
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: AppColors.danger.withOpacity(0.2), width: 1),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => _showMarkOldDialog(context),
          child: const Padding(
            padding: EdgeInsets.symmetric(vertical: 16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.no_accounts_rounded, color: AppColors.danger),
                SizedBox(width: 8),
                Text(
                  'Mark Student as Inactive / Exit',
                  style: TextStyle(color: AppColors.danger, fontWeight: FontWeight.bold, fontSize: 14),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showMarkOldDialog(BuildContext context) {
    String exitDateStr = DateFormat('yyyy-MM-dd').format(DateTime.now());
    bool isSaving = false;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (stContext, setDialogState) {
            return AlertDialog(
              title: const Text('Exit Library Registration'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('This will cancel all pending notices for this student, vacate their seat allocation, and mark their profile status as "Old Student".'),
                  const SizedBox(height: 16),
                  InkWell(
                    onTap: () async {
                      final picked = await showDatePicker(
                        context: context,
                        initialDate: DateTime.now(),
                        firstDate: DateTime(2020),
                        lastDate: DateTime(2030),
                      );
                      if (picked != null) {
                        setDialogState(() {
                          exitDateStr = DateFormat('yyyy-MM-dd').format(picked);
                        });
                      }
                    },
                    child: InputDecorator(
                      decoration: const InputDecoration(
                        labelText: 'Exit Date',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.calendar_today_rounded),
                      ),
                      child: Text(
                        exitDateStr,
                        style: const TextStyle(fontSize: 16),
                      ),
                    ),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: isSaving ? null : () => Navigator.pop(dialogContext),
                  child: const Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
                ),
                ElevatedButton(
                  onPressed: isSaving
                      ? null
                      : () async {
                          setDialogState(() {
                            isSaving = true;
                          });
                          try {
                            final success = await ApiService.markOldStudent(
                              widget.studentId,
                              exitDateStr,
                            );
                            if (success) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Student profile marked as inactive.'),
                                  backgroundColor: AppColors.success,
                                ),
                              );
                              Navigator.pop(dialogContext);
                              setState(() {
                                _anyChangesSaved = true;
                              });
                              _loadData(); // Reload details page to update status view
                            } else {
                              throw Exception('Failed to mark student as old.');
                            }
                          } catch (e) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('Error: ${e.toString()}'),
                                backgroundColor: AppColors.danger,
                              ),
                            );
                          } finally {
                            setDialogState(() {
                              isSaving = false;
                            });
                          }
                        },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.danger,
                    foregroundColor: Colors.white,
                  ),
                  child: isSaving
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : const Text('Confirm Exit'),
                ),
              ],
            );
          },
        );
      },
    );
  }
}
