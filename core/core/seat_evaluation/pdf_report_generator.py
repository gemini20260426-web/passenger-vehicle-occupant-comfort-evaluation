#!/usr/bin/env python3
"""
全量统计分析 PDF 报告生成器
用法:
    from pdf_report_generator import PDFReportGenerator
    gen = PDFReportGenerator(results)
    gen.generate('full_analysis_report.pdf')
"""

import os, json
from datetime import datetime
from io import BytesIO
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ── PDF ──
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

import logging
logger = logging.getLogger(__name__)

# ── 中文字体 ──
FONT_NAME = 'SimHei'  # 或 'Microsoft YaHei'


class PDFReportGenerator:
    """全量统计分析 PDF 报告生成器"""

    def __init__(self, results: dict, output_path: str = None):
        """
        Args:
            results: 全量统计分析结果字典 (来自 ReportBuilder.build())
            output_path: 输出路径
        """
        self.results = results
        self.output_path = output_path or 'full_analysis_report.pdf'
        self.styles = self._build_styles()
        self._chart_counter = 0

    def _build_styles(self):
        """构建报告样式"""
        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            'CoverTitle', parent=styles['Title'],
            fontName=FONT_NAME, fontSize=28, leading=36,
            alignment=TA_CENTER, textColor=HexColor('#2F5496'),
        ))
        styles.add(ParagraphStyle(
            'CoverSubtitle', parent=styles['Normal'],
            fontName=FONT_NAME, fontSize=14, leading=20,
            alignment=TA_CENTER, textColor=HexColor('#666666'),
        ))
        styles.add(ParagraphStyle(
            'ChapterTitle', parent=styles['Heading1'],
            fontName=FONT_NAME, fontSize=18, leading=24,
            textColor=HexColor('#2F5496'),
        ))
        styles.add(ParagraphStyle(
            'SectionTitle', parent=styles['Heading2'],
            fontName=FONT_NAME, fontSize=14, leading=20,
            textColor=HexColor('#333333'),
        ))
        styles.add(ParagraphStyle(
            'BodyCN', parent=styles['Normal'],
            fontName=FONT_NAME, fontSize=10, leading=16,
        ))
        styles.add(ParagraphStyle(
            'TableHeader', parent=styles['Normal'],
            fontName=FONT_NAME, fontSize=9, leading=12,
            textColor=white, alignment=TA_CENTER,
        ))
        styles.add(ParagraphStyle(
            'TableCell', parent=styles['Normal'],
            fontName=FONT_NAME, fontSize=8, leading=11,
        ))

        return styles

    # ═══════════════════════════════════════════
    # 主生成方法
    # ═══════════════════════════════════════════

    def generate(self) -> str:
        """生成完整 PDF 报告 → 返回文件路径"""
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=A4,
            topMargin=2 * cm, bottomMargin=1.5 * cm,
            leftMargin=2 * cm, rightMargin=2 * cm,
        )

        story = []

        # 封面
        story.extend(self._build_cover())
        story.append(PageBreak())

        # 目录
        story.extend(self._build_toc())
        story.append(PageBreak())

        # Ch1: 数据概览
        story.extend(self._build_chapter1())
        story.append(PageBreak())

        # Ch2: 驾驶事件分析
        story.extend(self._build_chapter2())
        story.append(PageBreak())

        # Ch3: 时域指标
        story.extend(self._build_chapter3())
        story.append(PageBreak())

        # Ch4: 频域指标
        story.extend(self._build_chapter4())
        story.append(PageBreak())

        # Ch5: 冲击与疲劳
        story.extend(self._build_chapter5())
        story.append(PageBreak())

        # Ch6: 衰减效率
        story.extend(self._build_chapter6())
        story.append(PageBreak())

        # Ch7: 统计检验
        story.extend(self._build_chapter7())
        story.append(PageBreak())

        # Ch8: 诊断与建议
        story.extend(self._build_chapter8())
        story.append(PageBreak())

        # Ch9: 舒适度指数 (新增)
        story.extend(self._build_chapter9())
        story.append(PageBreak())

        # Ch10: 脊柱健康 (ISO 2631-5，新增)
        if self.results.get('spine_health'):
            story.extend(self._build_chapter10())
            story.append(PageBreak())

        # Ch11: 平顺性 (GB/T 4970，新增)
        if self.results.get('ride_quality'):
            story.extend(self._build_chapter11())

        # ── 生成PDF ──
        doc.build(story)
        return self.output_path

    # ═══════════════════════════════════════════
    # 章节构建
    # ═══════════════════════════════════════════

    def _build_cover(self):
        """封面页"""
        return [
            Spacer(1, 6 * cm),
            Paragraph("乘用车座椅综合性能评测", self.styles['CoverTitle']),
            Spacer(1, 1 * cm),
            Paragraph("全量统计分析报告", self.styles['CoverTitle']),
            Spacer(1, 2 * cm),
            HRFlowable(width="60%", thickness=1, color=HexColor('#2F5496')),
            Spacer(1, 1.5 * cm),
            Paragraph(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                      self.styles['CoverSubtitle']),
            Paragraph(f"数据来源: {self._get_meta('data_sources', '—')}",
                      self.styles['CoverSubtitle']),
            Paragraph("分析引擎: 五层架构 + LightGBM ML",
                      self.styles['CoverSubtitle']),
            Spacer(1, 2 * cm),
            HRFlowable(width="60%", thickness=1, color=HexColor('#2F5496')),
        ]

    def _build_toc(self):
        """目录"""
        items = [
            "1. 数据概览",
            "2. 驾驶事件分析",
            "3. 时域指标 (ACC/VDV/HIC/DISP)",
            "4. 频域指标 (SEAT/TR/PSD)",
            "5. 冲击与疲劳 (SRS/FDS/S_d)",
            "6. 衰减效率 (E vs C)",
            "7. 统计检验",
            "8. 诊断与建议",
            "9. 舒适度综合指数",
            "10. 脊柱健康 (ISO 2631-5)",
            "11. 平顺性 (GB/T 4970)",
        ]
        story = [Paragraph("目  录", self.styles['ChapterTitle']), Spacer(1, 1 * cm)]
        for item in items:
            story.append(Paragraph(item, self.styles['SectionTitle']))
            story.append(Spacer(1, 0.3 * cm))
        return story

    def _build_chapter1(self):
        """数据概览"""
        story = [Paragraph("1. 数据概览", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]

        meta = self.results.get('metadata', {})
        evts = self.results.get('events', [])
        data = [
            ['项目', '详情'],
            ['数据来源', str(meta.get('source', '—'))],
            ['检测事件数', str(meta.get('total_events', len(evts) if evts else '—'))],
            ['事件类型数', str(len(meta.get('event_types', {})) if meta.get('event_types') else '—')],
            ['平均车速', f"{meta.get('speed_avg', '—')} km/h"],
            ['数据时长', f"{meta.get('duration_s', '—')} s"],
            ['采样率', f"{meta.get('sampling_rate', '—')} Hz"],
            ['生成时间', str(meta.get('created_at', '—'))[:19]],
        ]

        story.append(self._make_table(data, [5 * cm, 10 * cm]))
        return story

    def _build_chapter2(self):
        """驾驶事件分析"""
        story = [Paragraph("2. 驾驶事件分析", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]

        events = self.results.get('events', [])

        if events:
            # 事件分布图
            from collections import Counter
            event_types = [e.get('type', 'unknown') for e in events]
            counts = Counter(event_types)

            fig, ax = plt.subplots(figsize=(8, max(3, len(counts) * 0.4)))
            labels = list(counts.keys())
            values = list(counts.values())
            colors = plt.cm.RdYlGn(np.linspace(0.2, 0.8, len(labels)))

            bars = ax.barh(range(len(labels)), values, color=colors)
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontsize=9)
            ax.set_xlabel('事件数量', fontsize=10)

            img = self._fig_to_image(fig)
            story.append(img)
            plt.close(fig)

            # 事件详情表
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph("事件详情 (前30条)", self.styles['SectionTitle']))

            table_data = [['#', '类型', '时间(s)', '持续(s)', '置信度']]
            for i, e in enumerate(events[:30], 1):
                table_data.append([
                    str(i),
                    e.get('type', '—'),
                    f"{e.get('t_start', 0):.1f}",
                    f"{e.get('duration', 0):.1f}",
                    f"{e.get('confidence', 0):.1%}",
                ])

            story.append(self._make_table(table_data, [1 * cm, 4 * cm, 2.5 * cm, 2.5 * cm, 2 * cm]))

        return story

    def _build_chapter3(self):
        """时域指标"""
        story = [Paragraph("3. 时域指标", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]

        td = self.results.get('time_domain', {})

        # 峰值加速度表
        story.append(Paragraph("3.1 峰值加速度", self.styles['SectionTitle']))
        acc_data = [['位置', '组别', 'Ax(m/s²)', 'Ay(m/s²)', 'Az(m/s²)']]

        for pos_name, pos_data in td.get('acc_peak', {}).items():
            for group in ['实验组', '对照组']:
                g = pos_data.get(group, {})
                if not g:
                    continue
                acc_data.append([
                    pos_name, group,
                    f"{g.get('X', 0):.2f}",
                    f"{g.get('Y', 0):.2f}",
                    f"{g.get('Z', 0):.2f}",
                ])

        story.append(self._make_table(acc_data, [2.5 * cm, 2 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]))
        story.append(Spacer(1, 0.5 * cm))

        # VDV 表
        story.append(Paragraph("3.2 振动剂量值 VDV (m/s¹·⁷⁵)", self.styles['SectionTitle']))
        vdv_data = [['位置', '组别', 'X', 'Y', 'Z']]
        for pos_name, pos_data in td.get('vdv', {}).items():
            for group in ['实验组', '对照组']:
                g = pos_data.get(group, {})
                if not g:
                    continue
                vdv_data.append([
                    pos_name, group,
                    f"{g.get('X', 0):.2f}",
                    f"{g.get('Y', 0):.2f}",
                    f"{g.get('Z', 0):.2f}",
                ])
        story.append(self._make_table(vdv_data, [2.5 * cm, 2 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]))

        return story

    def _build_chapter4(self):
        """频域指标"""
        story = [Paragraph("4. 频域指标", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]

        fd = self.results.get('frequency_domain', {})

        # SEAT 表
        story.append(Paragraph("4.1 SEAT 因子", self.styles['SectionTitle']))
        seat_data = [['位置对', 'SEAT_X', 'SEAT_Y', 'SEAT_Z']]
        for pair_name, pair in fd.get('seat', {}).items():
            seat_data.append([
                pair_name,
                f"{pair.get('X', 0):.3f}",
                f"{pair.get('Y', 0):.3f}",
                f"{pair.get('Z', 0):.3f}",
            ])
        story.append(self._make_table(seat_data, [4 * cm, 3 * cm, 3 * cm, 3 * cm]))

        return story

    def _build_chapter5(self):
        """冲击与疲劳"""
        story = [Paragraph("5. 冲击与疲劳", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]

        sf = self.results.get('shock_fatigue', {})

        # S_d 脊柱健康
        story.append(Paragraph("5.1 脊柱压缩应力 S_d (ISO 2631-5)", self.styles['SectionTitle']))
        sd_data = [['位置', '组别', 'S_d (MPa)']]
        for pos_name, pos_data in sf.get('iso2631_5', {}).items():
            for group in ['实验组', '对照组']:
                g = pos_data.get(group, {})
                if not g:
                    continue
                sd_data.append([
                    pos_name, group,
                    f"{g.get('S_d', 0):.4f}",
                ])
        story.append(self._make_table(sd_data, [3 * cm, 3 * cm, 4 * cm]))

        return story

    def _build_chapter6(self):
        """衰减效率"""
        story = [Paragraph("6. 衰减效率 (E vs C)", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]

        atten = self.results.get('attenuation', {})

        atten_data = [['轴', '衰减率 (%)']]
        for axis, values in atten.items():
            atten_data.append([
                axis,
                f"{values.get('overall', 0):.1f}%",
            ])
        story.append(self._make_table(atten_data, [5 * cm, 5 * cm]))

        return story

    def _build_chapter7(self):
        """统计检验"""
        story = [Paragraph("7. 统计检验", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]

        stats = self.results.get('statistical_tests', {})

        t_test = stats.get('t_test', {})
        cohens_d = stats.get('cohens_d', {})
        sig_count = stats.get('significant_count', 0)

        stat_data = [['指标', 'p值', '显著性', "Cohen's d"]]
        for metric in t_test:
            p = t_test.get(metric, 1)
            sig = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'ns'
            d = cohens_d.get(metric, 0)
            stat_data.append([
                metric,
                f"{p:.4f}",
                sig,
                f"{d:.3f}",
            ])
        story.append(self._make_table(stat_data, [4 * cm, 2 * cm, 2 * cm, 2.5 * cm]))

        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(f"显著性指标数: {sig_count}", self.styles['BodyCN']))

        return story

    def _build_chapter8(self):
        """诊断与建议"""
        story = [Paragraph("8. 诊断与建议", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]

        tuning = self.results.get('tuning_recommendations', [])

        if tuning:
            for i, rec in enumerate(tuning, 1):
                rec_text = (
                    f"建议 {i}: {rec.get('component', '')} — {rec.get('parameter', '')}\n"
                    f"  调整方向: {rec.get('direction', '')}\n"
                    f"  置信度: {rec.get('confidence', 0):.0%}\n"
                    f"  原因: {rec.get('reason', '')}\n"
                    f"  预期效果: {rec.get('expected', '')}"
                )
                story.append(Paragraph(rec_text, self.styles['BodyCN']))
                story.append(Spacer(1, 0.3 * cm))
        else:
            story.append(Paragraph("✅ 所有指标在正常范围内，无需特别关注。", self.styles['BodyCN']))

        return story

    def _build_chapter9(self):
        """舒适度综合指数 (新增)"""
        story = [Paragraph("9. 舒适度综合指数", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]

        ci = self.results.get('comfort_index', {})
        sub = self.results.get('subjective', {})

        if ci:
            story.append(Paragraph(
                f"综合评分: {ci.get('overall_score', 0):.0f}/100  "
                f"等级: {ci.get('grade', 'N/A')}级  "
                f"({ci.get('grade_label', '')})",
                self.styles['SectionTitle']
            ))
            story.append(Spacer(1, 0.3 * cm))

            ci_data = [
                ['维度', '得分'],
                ['振动', f"{ci.get('vibration_score', 0):.0f}"],
                ['冲击', f"{ci.get('shock_score', 0):.0f}"],
                ['传递衰减', f"{ci.get('transfer_score', 0):.0f}"],
                ['姿态稳定', f"{ci.get('posture_score', 0):.0f}"],
            ]
            story.append(self._make_table(ci_data, [5 * cm, 5 * cm]))

        if sub:
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph("主观评价:", self.styles['SectionTitle']))
            story.append(Paragraph(sub.get('narrative', '—'), self.styles['BodyCN']))

        return story

    def _build_chapter10(self):
        """脊柱健康 (ISO 2631-5)"""
        story = [Paragraph("10. 脊柱健康 (ISO 2631-5)", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]
        sh = self.results.get('spine_health', {})
        if sh:
            story.append(Paragraph(
                f"风险等级: {sh.get('risk_label', '—')}  "
                f"(R={sh.get('risk_factor', 0):.3f})",
                self.styles['SectionTitle']
            ))
            story.append(Spacer(1, 0.3 * cm))
            sh_data = [
                ['指标', '数值'],
                ['等效应力 S_e', f"{sh.get('s_e', 0):.3f} MPa"],
                ['风险因子 R', f"{sh.get('risk_factor', 0):.3f}"],
                ['X轴剂量 D_x', f"{sh.get('d_x', 0):.2f}"],
                ['Y轴剂量 D_y', f"{sh.get('d_y', 0):.2f}"],
                ['Z轴剂量 D_z', f"{sh.get('d_z', 0):.2f}"],
                ['每日暴露限值', f"{sh.get('daily_exposure', '—')} h"],
            ]
            story.append(self._make_table(sh_data, [6 * cm, 6 * cm]))
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph(
                "注: 冲击得分(S_d)基于ISO 2631-1压缩应力评估，脊柱风险因子(R)基于ISO 2631-5 Annex C "
                "六次方剂量模型。S_d 反映单次冲击严重度，R 反映累积损伤风险。两者互补，需综合判断。",
                self.styles['BodyCN']
            ))
        return story

    def _build_chapter11(self):
        """平顺性 (GB/T 4970)"""
        story = [Paragraph("11. 平顺性 (GB/T 4970)", self.styles['ChapterTitle']), Spacer(1, 0.5 * cm)]
        rq = self.results.get('ride_quality', {})
        if rq:
            story.append(Paragraph(
                f"平顺性等级: {rq.get('comfort_label', '—')}",
                self.styles['SectionTitle']
            ))
            story.append(Spacer(1, 0.3 * cm))
            rq_data = [
                ['指标', '数值'],
                ['总加权加速度 a_w', f"{rq.get('aw_total', 0):.4f} m/s²"],
                ['X轴加权 a_wx', f"{rq.get('aw_x', 0):.4f} m/s²"],
                ['Y轴加权 a_wy', f"{rq.get('aw_y', 0):.4f} m/s²"],
                ['Z轴加权 a_wz', f"{rq.get('aw_z', 0):.4f} m/s²"],
            ]
            story.append(self._make_table(rq_data, [6 * cm, 6 * cm]))
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph(
                "注: 加权加速度 a_w 由VDV经时长转换近似得到 (aw = VDV / T^0.25)。"
                "精确值应从原始加速度数据经频率加权滤波后计算。",
                self.styles['BodyCN']
            ))
        return story

    # ═══════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════

    def _make_table(self, data, col_widths, header_color=HexColor('#2F5496')):
        """创建带样式的表格"""
        t = Table(data, colWidths=col_widths, repeatRows=1)
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F5F5F5')]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]
        t.setStyle(TableStyle(style))
        return t

    def _fig_to_image(self, fig, width=15 * cm, height=None):
        """matplotlib Figure → reportlab Image"""
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buf.seek(0)

        if height is None:
            height = width * fig.get_figheight() / fig.get_figwidth()

        return Image(buf, width=width, height=height)

    def _plot_band_radar(self, band_data):
        """绘制频段衰减雷达图"""
        categories = ['0.1-0.5Hz', '0.5-1Hz', '1-2Hz', '2-5Hz', '5-80Hz']
        N = len(categories)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

        for label, values in band_data.items():
            vals = [values.get(c, 0) for c in categories]
            vals += vals[:1]
            ax.fill(angles, vals, alpha=0.15)
            ax.plot(angles, vals, linewidth=2, label=label)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=9)
        ax.set_ylim(0, 100)
        ax.set_ylabel('衰减率 (%)', fontsize=10)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))

        return fig

    def _get_meta(self, key, default='—'):
        return self.results.get('metadata', {}).get(key, default)


class ReportService:
    """报告服务 — 从UI直接调用"""

    @staticmethod
    def export_pdf(analysis_results: dict, output_path: str = None) -> str:
        """导出 PDF 报告"""
        if output_path is None:
            os.makedirs('reports', exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'reports/full_analysis_{ts}.pdf'

        gen = PDFReportGenerator(analysis_results, output_path)
        path = gen.generate()
        return path

    @staticmethod
    def export_excel(analysis_results: dict, output_path: str = None) -> str:
        """导出 Excel 报告"""
        import pandas as pd

        if output_path is None:
            os.makedirs('reports', exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'reports/full_analysis_{ts}.xlsx'

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for section in ['events', 'time_domain', 'frequency_domain',
                             'shock_fatigue', 'attenuation', 'statistical_tests']:
                data = analysis_results.get(section, {})
                if data:
                    df = pd.json_normalize(data) if isinstance(data, list) else pd.DataFrame([data])
                    df.to_excel(writer, sheet_name=section, index=False)

        return output_path