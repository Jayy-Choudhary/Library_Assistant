import 'dart:math';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../theme/colors.dart';
import '../services/api_service.dart';

class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  Map<String, dynamic> _data = {};

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
      final data = await ApiService.getAnalyticsData();
      setState(() {
        _data = data;
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
        title: const Text('📈 Analytics'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh_rounded), onPressed: _loadData),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: AppColors.accent))
          : _errorMessage != null
              ? _buildError()
              : RefreshIndicator(
                  onRefresh: _loadData,
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildKeyMetricCards(),
                        const SizedBox(height: 20),
                        _buildRevenueChart(),
                        const SizedBox(height: 20),
                        _buildOccupancyGauge(),
                        const SizedBox(height: 20),
                        _buildFeeStatusDistribution(),
                        const SizedBox(height: 20),
                        _buildShiftDistribution(),
                        const SizedBox(height: 20),
                        _buildAdmissionsChart(),
                        const SizedBox(height: 32),
                      ],
                    ),
                  ),
                ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline_rounded, color: AppColors.danger, size: 64),
            const SizedBox(height: 16),
            Text(_errorMessage ?? '', textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textSecondary)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _loadData,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.accent, foregroundColor: Colors.white,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Key Metric Cards ───────────────────────────────────────────
  Widget _buildKeyMetricCards() {
    final totalRevenue = (_data['total_revenue'] ?? 0).toDouble();
    final activeStudents = _data['active_students'] ?? 0;
    final oldStudents = _data['old_students'] ?? 0;
    final occupancy = Map<String, dynamic>.from(_data['occupancy'] ?? {});
    final rate = (occupancy['rate'] ?? 0).toDouble();

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      childAspectRatio: 1.5,
      children: [
        _metricCard(
          'Total Revenue',
          '₹${NumberFormat('#,##,###').format(totalRevenue.toInt())}',
          Icons.account_balance_wallet_rounded,
          const Color(0xFF10B981),
          const Color(0xFF059669),
        ),
        _metricCard(
          'Occupancy Rate',
          '${rate.toStringAsFixed(1)}%',
          Icons.pie_chart_rounded,
          AppColors.accent,
          const Color(0xFF7C3AED),
        ),
        _metricCard(
          'Active Students',
          '$activeStudents',
          Icons.school_rounded,
          const Color(0xFF0EA5E9),
          const Color(0xFF0284C7),
        ),
        _metricCard(
          'Alumni',
          '$oldStudents',
          Icons.history_edu_rounded,
          const Color(0xFFF59E0B),
          const Color(0xFFD97706),
        ),
      ],
    );
  }

  Widget _metricCard(String label, String value, IconData icon, Color c1, Color c2) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [c1.withOpacity(0.12), c2.withOpacity(0.06)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: c1.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Flexible(
                child: Text(label, style: TextStyle(fontSize: 12, color: c1, fontWeight: FontWeight.w600)),
              ),
              Icon(icon, color: c1.withOpacity(0.7), size: 20),
            ],
          ),
          Text(
            value,
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, fontFamily: 'Georgia', color: c1),
          ),
        ],
      ),
    );
  }

  // ── Revenue Bar Chart ──────────────────────────────────────────
  Widget _buildRevenueChart() {
    final revenue = List<Map<String, dynamic>>.from(
      (_data['monthly_revenue'] ?? []).map((e) => Map<String, dynamic>.from(e)),
    );

    return _chartCard(
      title: 'Monthly Revenue',
      subtitle: 'Last 6 months collection trend',
      icon: Icons.trending_up_rounded,
      iconColor: const Color(0xFF10B981),
      child: SizedBox(
        height: 180,
        child: CustomPaint(
          size: const Size(double.infinity, 180),
          painter: _BarChartPainter(
            data: revenue.map((e) => (e['total'] as num).toDouble()).toList(),
            labels: revenue.map((e) => e['month'].toString()).toList(),
            barColor: const Color(0xFF10B981),
            textColor: AppColors.textSecondary,
          ),
        ),
      ),
    );
  }

  // ── Occupancy Gauge ────────────────────────────────────────────
  Widget _buildOccupancyGauge() {
    final occ = Map<String, dynamic>.from(_data['occupancy'] ?? {});
    final total = (occ['total'] ?? 0) as int;
    final occupied = (occ['occupied'] ?? 0) as int;
    final available = (occ['available'] ?? 0) as int;
    final rate = (occ['rate'] ?? 0).toDouble();

    return _chartCard(
      title: 'Seat Occupancy',
      subtitle: '$occupied of $total seats filled',
      icon: Icons.event_seat_rounded,
      iconColor: AppColors.accent,
      child: SizedBox(
        height: 160,
        child: Row(
          children: [
            Expanded(
              flex: 2,
              child: CustomPaint(
                size: const Size(140, 140),
                painter: _GaugePainter(
                  percentage: rate,
                  gaugeColor: rate > 85
                      ? AppColors.danger
                      : rate > 60
                          ? AppColors.warning
                          : AppColors.accent,
                  trackColor: AppColors.border,
                  textColor: AppColors.textPrimary,
                ),
              ),
            ),
            Expanded(
              flex: 3,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _gaugeDetail(Icons.event_seat, 'Occupied', '$occupied', AppColors.accent),
                  const SizedBox(height: 12),
                  _gaugeDetail(Icons.check_circle_outline, 'Available', '$available', AppColors.success),
                  const SizedBox(height: 12),
                  _gaugeDetail(Icons.grid_view_rounded, 'Total', '$total', AppColors.textSecondary),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _gaugeDetail(IconData icon, String label, String value, Color color) {
    return Row(
      children: [
        Container(
          width: 32, height: 32,
          decoration: BoxDecoration(
            color: color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, size: 16, color: color),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
        ),
        Text(value, style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: color)),
      ],
    );
  }

  // ── Fee Status Distribution ────────────────────────────────────
  Widget _buildFeeStatusDistribution() {
    final dist = Map<String, dynamic>.from(_data['fee_status_distribution'] ?? {});
    final entries = dist.entries.where((e) => (e.value as int) > 0).toList();
    final total = entries.fold<int>(0, (sum, e) => sum + (e.value as int));

    final colorMap = {
      'Paid': const Color(0xFF10B981),
      'Active': const Color(0xFF0EA5E9),
      'Reminder Due': const Color(0xFFFACC15),
      'Due': const Color(0xFFFB923C),
      'Overdue': const Color(0xFFEF4444),
    };

    return _chartCard(
      title: 'Fee Status',
      subtitle: 'Distribution across $total active students',
      icon: Icons.donut_large_rounded,
      iconColor: const Color(0xFFFB923C),
      child: Column(
        children: entries.map((entry) {
          final count = entry.value as int;
          final pct = total > 0 ? count / total : 0.0;
          final color = colorMap[entry.key] ?? AppColors.textSecondary;

          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(
              children: [
                Container(
                  width: 10, height: 10,
                  decoration: BoxDecoration(shape: BoxShape.circle, color: color),
                ),
                const SizedBox(width: 10),
                SizedBox(
                  width: 100,
                  child: Text(entry.key, style: const TextStyle(fontSize: 13, color: AppColors.textPrimary)),
                ),
                Expanded(
                  child: Stack(
                    children: [
                      Container(
                        height: 22,
                        decoration: BoxDecoration(
                          color: color.withOpacity(0.08),
                          borderRadius: BorderRadius.circular(6),
                        ),
                      ),
                      FractionallySizedBox(
                        widthFactor: pct,
                        child: Container(
                          height: 22,
                          decoration: BoxDecoration(
                            color: color.withOpacity(0.35),
                            borderRadius: BorderRadius.circular(6),
                            gradient: LinearGradient(
                              colors: [color.withOpacity(0.5), color.withOpacity(0.25)],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                SizedBox(
                  width: 40,
                  child: Text(
                    '$count',
                    textAlign: TextAlign.right,
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: color),
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  // ── Shift Distribution ─────────────────────────────────────────
  Widget _buildShiftDistribution() {
    final dist = Map<String, dynamic>.from(_data['shift_distribution'] ?? {});
    if (dist.isEmpty) return const SizedBox.shrink();

    final total = dist.values.fold<int>(0, (sum, v) => sum + (v as int));
    final shiftLabels = {
      'FULL_DAY': 'Full Day',
      'HALF_DAY_DAY': 'Day Shift',
      'HALF_DAY_NIGHT': 'Night Shift',
    };
    final shiftColors = {
      'FULL_DAY': const Color(0xFF8B5CF6),
      'HALF_DAY_DAY': const Color(0xFFF59E0B),
      'HALF_DAY_NIGHT': const Color(0xFF6366F1),
    };

    return _chartCard(
      title: 'Shift Distribution',
      subtitle: 'Student allocation across shifts',
      icon: Icons.access_time_filled_rounded,
      iconColor: const Color(0xFF8B5CF6),
      child: Row(
        children: dist.entries.map((entry) {
          final label = shiftLabels[entry.key] ?? entry.key;
          final count = entry.value as int;
          final pct = total > 0 ? (count / total * 100) : 0.0;
          final color = shiftColors[entry.key] ?? AppColors.accent;

          return Expanded(
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 4),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: color.withOpacity(0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: color.withOpacity(0.2)),
              ),
              child: Column(
                children: [
                  Icon(
                    entry.key == 'FULL_DAY'
                        ? Icons.wb_sunny_rounded
                        : entry.key == 'HALF_DAY_DAY'
                            ? Icons.light_mode_rounded
                            : Icons.nightlight_round,
                    color: color,
                    size: 28,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '$count',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, fontFamily: 'Georgia', color: color),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    label,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${pct.toStringAsFixed(0)}%',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: color.withOpacity(0.7)),
                  ),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  // ── Admissions Bar Chart ───────────────────────────────────────
  Widget _buildAdmissionsChart() {
    final admissions = List<Map<String, dynamic>>.from(
      (_data['monthly_admissions'] ?? []).map((e) => Map<String, dynamic>.from(e)),
    );

    return _chartCard(
      title: 'New Admissions',
      subtitle: 'Monthly student intake trend',
      icon: Icons.person_add_alt_1_rounded,
      iconColor: const Color(0xFF0EA5E9),
      child: SizedBox(
        height: 180,
        child: CustomPaint(
          size: const Size(double.infinity, 180),
          painter: _BarChartPainter(
            data: admissions.map((e) => (e['count'] as num).toDouble()).toList(),
            labels: admissions.map((e) => e['month'].toString()).toList(),
            barColor: const Color(0xFF0EA5E9),
            textColor: AppColors.textSecondary,
          ),
        ),
      ),
    );
  }

  // ── Shared Chart Card Container ────────────────────────────────
  Widget _chartCard({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color iconColor,
    required Widget child,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: iconColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: iconColor, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.bold, color: AppColors.textPrimary,
                    )),
                    Text(subtitle, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          child,
        ],
      ),
    );
  }
}


// ══════════════════════════════════════════════════════════════════
//  Custom Painters for Charts
// ══════════════════════════════════════════════════════════════════

/// Vertical bar chart painter
class _BarChartPainter extends CustomPainter {
  final List<double> data;
  final List<String> labels;
  final Color barColor;
  final Color textColor;

  _BarChartPainter({
    required this.data,
    required this.labels,
    required this.barColor,
    required this.textColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (data.isEmpty) return;

    final maxVal = data.reduce(max).clamp(1.0, double.infinity);
    final barWidth = (size.width - 40) / data.length * 0.6;
    final spacing = (size.width - 40) / data.length;
    const bottomPadding = 28.0;
    const topPadding = 24.0;
    final chartHeight = size.height - bottomPadding - topPadding;

    // Draw horizontal grid lines
    final gridPaint = Paint()
      ..color = textColor.withOpacity(0.1)
      ..strokeWidth = 1;

    for (int i = 0; i <= 4; i++) {
      final y = topPadding + chartHeight * (1 - i / 4);
      canvas.drawLine(Offset(30, y), Offset(size.width, y), gridPaint);
    }

    for (int i = 0; i < data.length; i++) {
      final x = 30 + spacing * i + (spacing - barWidth) / 2;
      final barHeight = (data[i] / maxVal) * chartHeight;
      final y = topPadding + chartHeight - barHeight;

      // Gradient bar
      final barRect = RRect.fromRectAndRadius(
        Rect.fromLTWH(x, y, barWidth, barHeight),
        const Radius.circular(6),
      );

      final barPaint = Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [barColor, barColor.withOpacity(0.5)],
        ).createShader(Rect.fromLTWH(x, y, barWidth, barHeight));

      canvas.drawRRect(barRect, barPaint);

      // Value text on top
      if (data[i] > 0) {
        final valuePainter = TextPainter(
          text: TextSpan(
            text: data[i] >= 1000
                ? '${(data[i] / 1000).toStringAsFixed(1)}k'
                : data[i].toStringAsFixed(0),
            style: TextStyle(fontSize: 10, color: barColor, fontWeight: FontWeight.bold),
          ),
          textDirection: ui.TextDirection.ltr,
        )..layout();
        valuePainter.paint(canvas, Offset(x + barWidth / 2 - valuePainter.width / 2, y - 16));
      }

      // Month label
      final labelPainter = TextPainter(
        text: TextSpan(
          text: labels[i],
          style: TextStyle(fontSize: 11, color: textColor, fontWeight: FontWeight.w500),
        ),
        textDirection: ui.TextDirection.ltr,
      )..layout();
      labelPainter.paint(
        canvas,
        Offset(x + barWidth / 2 - labelPainter.width / 2, size.height - bottomPadding + 6),
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}


/// Circular gauge painter
class _GaugePainter extends CustomPainter {
  final double percentage;
  final Color gaugeColor;
  final Color trackColor;
  final Color textColor;

  _GaugePainter({
    required this.percentage,
    required this.gaugeColor,
    required this.trackColor,
    required this.textColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = min(size.width, size.height) / 2 - 16;

    // Track
    final trackPaint = Paint()
      ..color = trackColor.withOpacity(0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 14
      ..strokeCap = StrokeCap.round;

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -pi * 0.75,
      pi * 1.5,
      false,
      trackPaint,
    );

    // Filled arc
    final fillPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 14
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        startAngle: -pi * 0.75,
        endAngle: pi * 0.75,
        colors: [gaugeColor.withOpacity(0.6), gaugeColor],
      ).createShader(Rect.fromCircle(center: center, radius: radius));

    final sweepAngle = pi * 1.5 * (percentage / 100).clamp(0.0, 1.0);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -pi * 0.75,
      sweepAngle,
      false,
      fillPaint,
    );

    // Center text
    final valuePainter = TextPainter(
      text: TextSpan(
        text: '${percentage.toStringAsFixed(0)}%',
        style: TextStyle(
          fontSize: 26,
          fontWeight: FontWeight.bold,
          fontFamily: 'Georgia',
          color: gaugeColor,
        ),
      ),
      textDirection: ui.TextDirection.ltr,
    )..layout();
    valuePainter.paint(canvas, Offset(center.dx - valuePainter.width / 2, center.dy - valuePainter.height / 2 - 4));

    final labelPainter = TextPainter(
      text: TextSpan(
        text: 'occupied',
        style: TextStyle(fontSize: 10, color: textColor.withOpacity(0.5)),
      ),
      textDirection: ui.TextDirection.ltr,
    )..layout();
    labelPainter.paint(canvas, Offset(center.dx - labelPainter.width / 2, center.dy + 14));
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}
