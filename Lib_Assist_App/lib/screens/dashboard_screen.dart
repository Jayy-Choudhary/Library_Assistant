import 'package:flutter/material.dart';
import '../theme/colors.dart';
import '../services/api_service.dart';
import 'settings_screen.dart';
import 'rooms_screen.dart';
import 'analytics_screen.dart';



class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  Map<String, dynamic> _metrics = {};

  @override
  void initState() {
    super.initState();
    _loadMetrics();
  }

  Future<void> _loadMetrics() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final data = await ApiService.getDashboardMetrics();
      setState(() {
        _metrics = data;
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('📊 Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.analytics_outlined),
            tooltip: 'Analytics & Reports',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const AnalyticsScreen(),
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Connection Settings',
            onPressed: () async {
              final result = await Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const SettingsScreen(),
                ),
              );
              if (result == true) {
                _loadMetrics();
              }
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadMetrics,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? _buildErrorView()
              : RefreshIndicator(
                  onRefresh: _loadMetrics,
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: 16),
                        _buildStatGrid(),
                        const SizedBox(height: 8),
                        _buildRoomsLayoutCard(),
                        const SizedBox(height: 8),
                        _buildDueStudentsCard(),
                        const SizedBox(height: 24),
                      ],
                    ),
                  ),
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
              'Failed to load metrics',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
            ),
            const SizedBox(height: 8),
            Text(
              _errorMessage ?? 'Unknown error',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _loadMetrics,
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

  Widget _buildStatGrid() {
    final List<Map<String, dynamic>> cardItems = [
      {'title': 'Total Seats', 'val': _metrics['total_seats'] ?? 0, 'color': AppColors.accent, 'icon': Icons.chair},
      {'title': 'Occupied', 'val': _metrics['occupied_seats'] ?? 0, 'color': AppColors.accent2, 'icon': Icons.event_seat},
      {'title': 'Available', 'val': _metrics['available_seats'] ?? 0, 'color': AppColors.success, 'icon': Icons.check_circle},
      {'title': 'Active Students', 'val': _metrics['active_students'] ?? 0, 'color': const Color(0xFF0EA5E9), 'icon': Icons.school},
      {'title': 'Pending Notices', 'val': _metrics['pending_notices'] ?? 0, 'color': AppColors.warning, 'icon': Icons.pending_actions},
      {'title': 'Reminder Due', 'val': _metrics['reminder_due'] ?? 0, 'color': const Color(0xFFCA8A04), 'icon': Icons.campaign},
      {'title': 'Due', 'val': _metrics['due_notices'] ?? 0, 'color': const Color(0xFFEA580C), 'icon': Icons.warning_amber_rounded},
      {'title': 'Overdue', 'val': _metrics['overdue_notices'] ?? 0, 'color': AppColors.danger, 'icon': Icons.gavel_rounded},
    ];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.45,
        ),
        itemCount: cardItems.length,
        itemBuilder: (context, idx) {
          final item = cardItems[idx];
          return Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.cardBg,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      item['title'],
                      style: const TextStyle(fontSize: 13, color: AppColors.textSecondary, fontWeight: FontWeight.w500),
                    ),
                    Icon(item['icon'], color: item['color'].withOpacity(0.8), size: 20),
                  ],
                ),
                Text(
                  '${item['val']}',
                  style: TextStyle(
                    fontFamily: 'Georgia',
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                    color: item['color'],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildDueStudentsCard() {
    final List<dynamic> dueStudents = _metrics['due_students'] ?? [];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.money_off_rounded, color: AppColors.danger, size: 22),
                SizedBox(width: 8),
                Text(
                  'Fee Due Students',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
              ],
            ),
            const Divider(color: AppColors.border, height: 24),
            if (dueStudents.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 24.0),
                child: Center(
                  child: Text('No student has fees due.', style: TextStyle(color: AppColors.textSecondary)),
                ),
              )
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: dueStudents.length,
                separatorBuilder: (context, index) => const Divider(color: AppColors.border, height: 1),
                itemBuilder: (context, idx) {
                  final student = dueStudents[idx];
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12.0),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            Container(
                              width: 38,
                              height: 38,
                              decoration: BoxDecoration(
                                color: AppColors.accent.withOpacity(0.1),
                                shape: BoxShape.circle,
                              ),
                              alignment: Alignment.center,
                              child: Text(
                                student['seat_number'] ?? '',
                                style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.accent, fontSize: 13),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Text(
                              student['full_name'] ?? '',
                              style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.textPrimary),
                            ),
                          ],
                        ),
                        Text(
                          '₹${(student['due_amount'] as num).toStringAsFixed(0)}',
                          style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.danger, fontSize: 15),
                        ),
                      ],
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildRoomsLayoutCard() {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () async {
          await Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => const RoomsScreen(),
            ),
          );
          _loadMetrics();
        },
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: const BoxDecoration(
                  color: AppColors.accent,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.map_rounded, color: Colors.white, size: 24),
              ),
              const SizedBox(width: 16),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Interactive Room Map',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'View visual seat grid layouts for Rooms A, B & C.',
                      style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: AppColors.textSecondary),
            ],
          ),
        ),
      ),
    );
  }
}
