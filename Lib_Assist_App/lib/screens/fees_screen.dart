import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../theme/colors.dart';
import '../services/api_service.dart';
import 'student_detail_screen.dart';

class FeesScreen extends StatefulWidget {
  const FeesScreen({super.key});

  @override
  State<FeesScreen> createState() => _FeesScreenState();
}

class _FeesScreenState extends State<FeesScreen> with SingleTickerProviderStateMixin {
  bool _isLoading = true;
  String? _errorMessage;
  List<Map<String, dynamic>> _feeRows = [];
  String _filter = 'All'; // All, Due Only
  late TabController _tabController;

  final List<Map<String, dynamic>> _filterTabs = [
    {'label': 'All', 'icon': Icons.list_alt_rounded},
    {'label': 'Due Only', 'icon': Icons.warning_amber_rounded},
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _filterTabs.length, vsync: this);
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) {
        setState(() {
          _filter = _filterTabs[_tabController.index]['label'];
        });
      }
    });
    _loadFees();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadFees() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      // Trigger server-side notice generation first
      await ApiService.generateFeeNotices();

      // Fetch all fee rows
      final rawRows = await ApiService.getFeesWithStudents();
      
      // Fetch status for each student
      List<Map<String, dynamic>> enrichedRows = [];
      for (final raw in rawRows) {
        final row = Map<String, dynamic>.from(raw);
        final studentId = int.parse(row['student_id'].toString());
        try {
          row['status'] = await ApiService.getFeeStatus(studentId);
        } catch (_) {
          row['status'] = 'Active';
        }
        enrichedRows.add(row);
      }

      setState(() {
        _feeRows = enrichedRows;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  List<Map<String, dynamic>> get _filteredRows {
    if (_filter == 'Due Only') {
      return _feeRows.where((r) {
        final status = r['status']?.toString() ?? '';
        return status == 'Reminder Due' || status == 'Due' || status == 'Overdue';
      }).toList();
    }
    return _feeRows;
  }

  // Summary counters
  Map<String, int> get _statusCounts {
    final counts = <String, int>{
      'Paid': 0,
      'Reminder Due': 0,
      'Due': 0,
      'Overdue': 0,
      'Active': 0,
    };
    for (final row in _feeRows) {
      final status = row['status']?.toString() ?? 'Active';
      counts[status] = (counts[status] ?? 0) + 1;
    }
    return counts;
  }

  double get _totalDueAmount {
    double total = 0;
    for (final row in _feeRows) {
      total += double.tryParse(row['due_amount']?.toString() ?? '0') ?? 0;
    }
    return total;
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'Paid':
        return AppColors.success;
      case 'Reminder Due':
        return const Color(0xFFFACC15);
      case 'Due':
        return const Color(0xFFFB923C);
      case 'Overdue':
        return AppColors.danger;
      case 'Cancelled':
        return AppColors.textSecondary;
      default:
        return AppColors.accent;
    }
  }

  IconData _statusIcon(String status) {
    switch (status) {
      case 'Paid':
        return Icons.check_circle_rounded;
      case 'Reminder Due':
        return Icons.campaign_rounded;
      case 'Due':
        return Icons.warning_amber_rounded;
      case 'Overdue':
        return Icons.gavel_rounded;
      case 'Cancelled':
        return Icons.cancel_rounded;
      default:
        return Icons.schedule_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('💰 Fee Management'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _loadFees,
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: Container(
            color: AppColors.primary.withOpacity(0.8),
            child: TabBar(
              controller: _tabController,
              indicatorColor: Colors.white,
              indicatorWeight: 3,
              labelColor: Colors.white,
              unselectedLabelColor: Colors.white54,
              labelStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              tabs: _filterTabs.map((t) => Tab(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(t['icon'], size: 18),
                    const SizedBox(width: 6),
                    Text(t['label']),
                  ],
                ),
              )).toList(),
            ),
          ),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: AppColors.accent))
          : _errorMessage != null
              ? _buildErrorView()
              : RefreshIndicator(
                  onRefresh: _loadFees,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    children: [
                      _buildSummaryStrip(),
                      _buildFeeList(),
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
    );
  }

  Widget _buildErrorView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline_rounded, color: AppColors.danger, size: 64),
            const SizedBox(height: 16),
            const Text(
              'Failed to load fee data',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
            ),
            const SizedBox(height: 8),
            Text(
              _errorMessage ?? '',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _loadFees,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.accent,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSummaryStrip() {
    final counts = _statusCounts;
    final totalDue = _totalDueAmount;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Column(
        children: [
          // Total Due Banner
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  totalDue > 0 ? const Color(0xFFDC2626).withOpacity(0.12) : AppColors.success.withOpacity(0.12),
                  totalDue > 0 ? const Color(0xFFEA580C).withOpacity(0.06) : AppColors.success.withOpacity(0.06),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: totalDue > 0 ? const Color(0xFFDC2626).withOpacity(0.2) : AppColors.success.withOpacity(0.2),
              ),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: (totalDue > 0 ? AppColors.danger : AppColors.success).withOpacity(0.15),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    totalDue > 0 ? Icons.account_balance_wallet_rounded : Icons.check_circle_rounded,
                    color: totalDue > 0 ? AppColors.danger : AppColors.success,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        totalDue > 0 ? 'Total Outstanding' : 'All Fees Clear',
                        style: TextStyle(
                          fontSize: 13,
                          color: totalDue > 0 ? AppColors.danger : AppColors.success,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '₹${NumberFormat('#,##,###').format(totalDue.toInt())}',
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                          fontFamily: 'Georgia',
                          color: totalDue > 0 ? AppColors.danger : AppColors.success,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Status chips row
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _buildStatusChip('Paid', counts['Paid'] ?? 0, AppColors.success),
                _buildStatusChip('Reminder', counts['Reminder Due'] ?? 0, const Color(0xFFFACC15)),
                _buildStatusChip('Due', counts['Due'] ?? 0, const Color(0xFFFB923C)),
                _buildStatusChip('Overdue', counts['Overdue'] ?? 0, AppColors.danger),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusChip(String label, int count, Color color) {
    return Container(
      margin: const EdgeInsets.only(right: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(shape: BoxShape.circle, color: color),
          ),
          const SizedBox(width: 6),
          Text(
            '$label: $count',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeeList() {
    final rows = _filteredRows;

    if (rows.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 60),
        child: Center(
          child: Column(
            children: [
              Icon(
                _filter == 'Due Only' ? Icons.celebration_rounded : Icons.receipt_long_rounded,
                size: 56,
                color: AppColors.textSecondary.withOpacity(0.3),
              ),
              const SizedBox(height: 12),
              Text(
                _filter == 'Due Only' ? 'No dues pending! 🎉' : 'No fee records found',
                style: const TextStyle(color: AppColors.textSecondary, fontSize: 15),
              ),
            ],
          ),
        ),
      );
    }

    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: rows.length,
      itemBuilder: (context, idx) => _buildFeeCard(rows[idx]),
    );
  }

  Widget _buildFeeCard(Map<String, dynamic> row) {
    final studentId = int.parse(row['student_id'].toString());
    final seatNumber = row['seat_number']?.toString() ?? '—';
    final fullName = row['full_name']?.toString() ?? 'Unknown';
    final monthlyFee = double.tryParse(row['monthly_fee']?.toString() ?? '0') ?? 0;
    final dueAmount = double.tryParse(row['due_amount']?.toString() ?? '0') ?? 0;
    final dueDate = row['due_date']?.toString();
    final lastPayment = row['last_payment_date']?.toString();
    final status = row['status']?.toString() ?? 'Active';
    final color = _statusColor(status);
    final icon = _statusIcon(status);

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () async {
          final changed = await Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => StudentDetailScreen(studentId: studentId)),
          );
          if (changed == true) _loadFees();
        },
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header row: Name + Status Badge
              Row(
                children: [
                  // Seat badge
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      seatNumber,
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                        color: color,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  // Name
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          fullName,
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 15,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '₹${monthlyFee.toStringAsFixed(0)}/month',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  // Status badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: color.withOpacity(0.3)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(icon, size: 14, color: color),
                        const SizedBox(width: 4),
                        Text(
                          status,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: color,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),

              // Due amount + dates row
              if (dueAmount > 0 || dueDate != null || lastPayment != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.bg.withOpacity(0.6),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      // Due amount
                      Expanded(
                        child: _buildDetailItem(
                          'Due Amount',
                          '₹${dueAmount.toStringAsFixed(0)}',
                          dueAmount > 0 ? AppColors.danger : AppColors.success,
                        ),
                      ),
                      // Due date
                      if (dueDate != null)
                        Expanded(
                          child: _buildDetailItem(
                            'Due Date',
                            _formatDate(dueDate),
                            AppColors.textSecondary,
                          ),
                        ),
                      // Last payment
                      Expanded(
                        child: _buildDetailItem(
                          'Last Paid',
                          lastPayment != null ? _formatDate(lastPayment) : '—',
                          AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDetailItem(String label, String value, Color valueColor) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: AppColors.textSecondary),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: valueColor,
          ),
        ),
      ],
    );
  }

  String _formatDate(String dateStr) {
    try {
      final dt = DateTime.parse(dateStr);
      return DateFormat('dd MMM yyyy').format(dt);
    } catch (_) {
      return dateStr;
    }
  }
}
