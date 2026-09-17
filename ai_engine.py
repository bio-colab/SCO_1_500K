"""
AI Circuit Doctor - Comprehensive Hardware Fault Diagnostic Engine
Author: Antigravity Engineering
------------------------------------------------------------------
Automates electronic troubleshooting using live oscilloscope measurements.
Calculates Health Score (0-100%), identifies failure root causes,
and provides actionable repair recommendations in Arabic and English.
"""

from typing import Dict, Any, List

CIRCUIT_PROFILES = {
    "5V_RAIL": {
        "id": "5V_RAIL",
        "name_ar": "خط تغذية 5.0V (VCC / Logic)",
        "name_en": "5.0V Main Power Rail (VCC)",
        "type": "DC",
        "expected_v": 5.0,
        "tolerance_pct": 5.0,
        "max_ripple_v": 0.120,
        "desc_ar": "خط التغذية القياسي 5 فولت لدوائر المنطق والمتحكمات وحساسات الأردينو."
    },
    "3V3_RAIL": {
        "id": "3V3_RAIL",
        "name_ar": "خط تغذية 3.3V (LDO / MCU)",
        "name_en": "3.3V Logic Rail / LDO",
        "type": "DC",
        "expected_v": 3.3,
        "tolerance_pct": 5.0,
        "max_ripple_v": 0.060,
        "desc_ar": "خط تغذية المعالجات الحديثة (STM32, ESP32, CH32) ومنظمات الجهد LDO."
    },
    "1V8_RAIL": {
        "id": "1V8_RAIL",
        "name_ar": "خط جهد القلب 1.8V (Core Voltage)",
        "name_en": "1.8V Core / RAM Rail",
        "type": "DC",
        "expected_v": 1.8,
        "tolerance_pct": 4.0,
        "max_ripple_v": 0.035,
        "desc_ar": "جهد التغذية الحساس لأنوية المعالجات وذواكر DDR والشرائح المتقدمة."
    },
    "12V_RAIL": {
        "id": "12V_RAIL",
        "name_ar": "خط تغذية 12V (محركات / سيارات / باور)",
        "name_en": "12.0V Supply Rail / Power Stage",
        "type": "DC",
        "expected_v": 12.0,
        "tolerance_pct": 10.0,
        "max_ripple_v": 0.350,
        "desc_ar": "خط 12 فولت لتغذية الريليهات والمراوح ومراحل القدرة والسيارات."
    },
    "USB_5V": {
        "id": "USB_5V",
        "name_ar": "جهد منفذ الـ USB (VBUS 5V)",
        "name_en": "USB Port VBUS (5V)",
        "type": "DC",
        "expected_v": 5.0,
        "tolerance_pct": 5.0,
        "max_ripple_v": 0.100,
        "desc_ar": "خط الطاقة القادم من شواحن ومنافذ الـ USB (4.75V - 5.25V)."
    },
    "CLOCK_XTAL": {
        "id": "CLOCK_XTAL",
        "name_ar": "إشارة الساعة / الكريستالة (Clock / XTAL)",
        "name_en": "Clock Generator / Crystal Oscillator",
        "type": "AC_CLOCK",
        "min_freq_hz": 1000.0,
        "min_amplitude_v": 0.5,
        "desc_ar": "مذبذبات التردد وكريستالات التوقيت للميكروكنترولر والدوائر الرقمية."
    },
    "PWM_SIGNAL": {
        "id": "PWM_SIGNAL",
        "name_ar": "إشارة تعديل عرض النبضة (PWM)",
        "name_en": "PWM Control Signal",
        "type": "PWM",
        "min_amplitude_v": 1.0,
        "desc_ar": "إشارات التحكم في سرعة المحركات، إضاءة الـ LED، والإنفرتر."
    },
    "CUSTOM": {
        "id": "CUSTOM",
        "name_ar": "فحص مخصص (Custom Probe)",
        "name_en": "Custom Defined Target",
        "type": "DC",
        "expected_v": 5.0,
        "tolerance_pct": 5.0,
        "max_ripple_v": 0.100,
        "desc_ar": "إدخال يدوي للجهد المتوقع ونسبة التسامح والتموج."
    }
}

class AICircuitDoctor:
    @staticmethod
    def get_profiles() -> List[Dict[str, Any]]:
        return list(CIRCUIT_PROFILES.values())

    @staticmethod
    def diagnose_point(profile_id: str, m: Dict[str, Any], custom_params: Dict[str, Any] = None) -> Dict[str, Any]:
        # Check if hardware is offline (Reviewer Point 2 Fix)
        if m.get("connected") is False:
            prof_name = CIRCUIT_PROFILES.get(profile_id, CIRCUIT_PROFILES["5V_RAIL"])["name_ar"]
            return {
                "profile_id": profile_id,
                "profile_name_ar": prof_name,
                "profile_name_en": "Hardware Offline",
                "health_score": 0,
                "severity": "OFFLINE",
                "status_title_ar": "الجهاز غير متصل بالحاسوب (Hardware Offline)",
                "status_title_en": "Oscilloscope Hardware is Disconnected or Offline",
                "findings": [{
                    "level": "INFO",
                    "title_ar": "العتاد غير متصل أو مطفأ",
                    "title_en": "Hardware Offline Or Powered Down",
                    "detail_ar": "الخادم يعمل ولكن لا يستقبل بيانات من جهاز الأوسيلوسكوب. تأكد من تشغيل الجهاز بالزر وتوصيل أسلاك السيريال (TX/RX/GND).",
                    "detail_en": "Serial port is offline. Ensure oscilloscope is powered ON and UART wiring is secure."
                }],
                "recommendations": [{
                    "step_ar": "تأكد من أن مفتاح الطاقة الصغير (Power Switch) أعلى منفذ Type-C في وضع التشغيل (ON).",
                    "step_en": "Ensure device power switch is ON and battery/Type-C is connected."
                }, {
                    "step_ar": "تحقق من سلامة توصيل الأسلاك: طرف TX في اللوحة -> طرف RX في المحول، وطرف RX -> طرف TX، والأرضي GND بـ BNC.",
                    "step_en": "Check wiring: Scope TX -> Adapter RX, Scope RX -> Adapter TX, GND to BNC shield."
                }],
                "telemetry_snapshot": m
            }

        unknown_profile_warning = False
        if profile_id not in CIRCUIT_PROFILES and profile_id != "CUSTOM":
            unknown_profile_warning = True
            profile = dict(CIRCUIT_PROFILES["5V_RAIL"])
        else:
            profile = dict(CIRCUIT_PROFILES.get(profile_id, CIRCUIT_PROFILES["5V_RAIL"]))
        
        # Safe handling of custom parameters (Issue 6 fix)
        if profile_id == "CUSTOM" and custom_params:
            try:
                ev = float(custom_params.get("expected_v", 5.0))
                profile["expected_v"] = ev if ev > 0 else 5.0
            except (ValueError, TypeError):
                profile["expected_v"] = 5.0

            try:
                tol = float(custom_params.get("tolerance_pct", 5.0))
                profile["tolerance_pct"] = tol if 0 < tol <= 100 else 5.0
            except (ValueError, TypeError):
                profile["tolerance_pct"] = 5.0

            try:
                rip = float(custom_params.get("max_ripple_v", 0.1))
                profile["max_ripple_v"] = rip if rip >= 0 else 0.1
            except (ValueError, TypeError):
                profile["max_ripple_v"] = 0.1

        # Safe telemetry values
        def safe_float(val, default=0.0):
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        vmax = safe_float(m.get("v_max", 0.0))
        vmin = safe_float(m.get("v_min", 0.0))
        vave = safe_float(m.get("v_ave", 0.0))
        vpp  = safe_float(m.get("v_pp", 0.0))
        vrms = safe_float(m.get("v_rms", 0.0))
        freq = safe_float(m.get("frequency_hz", 0.0))
        period = safe_float(m.get("period_us", 0.0))
        duty_pos = safe_float(m.get("duty_pos_pct", 0.0))

        health_score = 100
        findings = []
        recommendations = []
        p_type = profile.get("type", "DC")

        # ==========================================
        # 1. DC POWER RAIL ANALYSIS (Issue 2 Fix)
        # ==========================================
        if p_type == "DC":
            exp_v = profile["expected_v"]
            tol_pct = profile["tolerance_pct"]
            max_ripple = profile["max_ripple_v"]
            min_allowed = exp_v * (1.0 - tol_pct / 100.0)
            max_allowed = exp_v * (1.0 + tol_pct / 100.0)

            # Deviation is always measured relative to the profile's own tolerance
            # window. A fixed 10% cut-off would make the "moderate" tier
            # unreachable for any profile whose tolerance is >= 10% (e.g. 12V).
            # A deviation is "severe" only once it is twice the allowed tolerance,
            # with a 10% floor for very tight rails (1.8V core @ 4%).
            severe_ratio = max(0.10, 2.0 * tol_pct / 100.0)
            deviation = ((vave - exp_v) / exp_v) if exp_v > 0 else 0.0
            drop_pct = -deviation * 100.0
            over_pct = deviation * 100.0

            # A. Dead Rail Check (0V)
            # Evaluate using vave and vmax together
            if vave < 0.25 and vmax < 0.35:
                health_score = 0
                findings.append({
                    "level": "CRITICAL",
                    "title_ar": "غياب تام للجهد (Dead Rail / 0V)",
                    "title_en": "Dead Rail (0V) - Short to GND or Open Circuit",
                    "detail_ar": f"متوسط الجهد المقاس {vave:.3f}V بينما المتوقع {exp_v:.2f}V. خط التغذية مفصول أو به قصر صريح (Short to GND).",
                    "detail_en": f"Measured average voltage is {vave:.3f}V vs nominal {exp_v:.2f}V. Power rail is dead."
                })
                recommendations.append({
                    "step_ar": "افصل التغذية فوراً وافحص المقاومة بين هذا الخط والأرضي (GND) بوضع الجرس/الدايود في الملتيميتر.",
                    "step_en": "Cut power and measure resistance from this rail to GND in diode/continuity mode."
                })
                recommendations.append({
                    "step_ar": "إذا رن الجرس (أقل من 5 أوم)، افحص المكثفات السيراميكية (MLCC) أو الشرائح المتصلة بالخط.",
                    "step_en": "If continuity beeps (< 5 ohms), inspect ceramic decoupling capacitors or shorted ICs."
                })
                recommendations.append({
                    "step_ar": "إذا لم يوجد قصر، افحص فيوز الحماية أو منظم الجهد أو طرف التمكين (Enable).",
                    "step_en": "If no short, verify input fuse, upstream regulator enable pin, or broken trace."
                })

            # B. Severe Voltage Sag (below tolerance AND deviating by >= severe_ratio)
            elif vave < min_allowed and (-deviation) >= severe_ratio:
                health_score = max(10, health_score - 65)
                findings.append({
                    "level": "CRITICAL",
                    "title_ar": f"هبوط حاد في الجهد بنسبة {drop_pct:.1f}% (Severe Voltage Sag)",
                    "title_en": f"Severe Voltage Sag ({drop_pct:.1f}% below nominal)",
                    "detail_ar": f"متوسط الجهد {vave:.3f}V منهار تحت الحد الأدنى الآمن ({min_allowed:.2f}V). الخط يعاني من سحب تيار مفرط أو عجز في المنظم.",
                    "detail_en": f"Average DC voltage {vave:.3f}V is severely below minimum {min_allowed:.2f}V (-{drop_pct:.1f}% drop)."
                })
                recommendations.append({
                    "step_ar": "تحقق من حرارة العناصر على هذا الخط باللمس أو الكاميرا الحرارية لرصد السحب الزائد (Overload).",
                    "step_en": "Check component temperatures on this rail; excessive heat indicates heavy overload."
                })
                recommendations.append({
                    "step_ar": "افحص ملف الخرج (Inductor) ومكثفات التغذية لمنظم الخفض (Buck Converter).",
                    "step_en": "Inspect buck converter switching inductor and filtering stage."
                })

            # C. Moderate Voltage Sag
            elif vave < min_allowed:
                health_score = max(45, health_score - 35)
                findings.append({
                    "level": "WARNING",
                    "title_ar": f"انخفاض طفيف في الجهد بنسبة {drop_pct:.1f}% (Voltage Sag)",
                    "title_en": f"Moderate Voltage Sag ({drop_pct:.1f}% below nominal)",
                    "detail_ar": f"متوسط الجهد {vave:.3f}V أقل من نافذة التسامح ({min_allowed:.2f}V - {max_allowed:.2f}V).",
                    "detail_en": f"Average voltage {vave:.3f}V is below nominal lower bound {min_allowed:.2f}V."
                })
                recommendations.append({
                    "step_ar": "تأكد من سلامة مقاومات مجزئ التغذية الراجعة (Feedback Resistors) لمنظم الجهد.",
                    "step_en": "Check feedback voltage divider network resistors around the voltage regulator."
                })

            # D. DC Over-Voltage (vave above upper tolerance), same two tiers as the sag path
            elif vave > max_allowed and deviation >= severe_ratio:
                health_score = max(10, health_score - 70)
                findings.append({
                    "level": "CRITICAL",
                    "title_ar": f"ارتفاع خطر في الجهد المستمر بنسبة +{over_pct:.1f}% (DC Over-Voltage)",
                    "title_en": f"Dangerous DC Over-Voltage (+{over_pct:.1f}% above nominal)",
                    "detail_ar": f"متوسط الجهد {vave:.3f}V يتجاوز الحد الأقصى ({max_allowed:.2f}V). خطر احتراق الدوائر المتكاملة والأنوية!",
                    "detail_en": f"Average voltage {vave:.3f}V exceeds maximum safety threshold ({max_allowed:.2f}V)."
                })
                recommendations.append({
                    "step_ar": "افصل التغذية فوراً! منظم الجهد به عطل في حلقة التغذية أو قصر بين الدخل والخرج (Mosfet Short).",
                    "step_en": "Power down immediately! Regulator high-side MOSFET may have punched through."
                })

            elif vave > max_allowed:
                health_score = max(45, health_score - 35)
                findings.append({
                    "level": "WARNING",
                    "title_ar": f"ارتفاع في الجهد المستمر بنسبة +{over_pct:.1f}% (Elevated DC Level)",
                    "title_en": f"Elevated DC Level (+{over_pct:.1f}% above nominal)",
                    "detail_ar": f"متوسط الجهد {vave:.3f}V أعلى من نافذة التسامح ({min_allowed:.2f}V - {max_allowed:.2f}V) دون أن يبلغ حدّ الخطر.",
                    "detail_en": f"Average voltage {vave:.3f}V is above the tolerance window but below the danger threshold."
                })
                recommendations.append({
                    "step_ar": "افحص مقاومات مجزئ التغذية الراجعة للمنظم، وتحقق من معايرة المجسّ قبل استبدال أي عنصر.",
                    "step_en": "Check the regulator feedback divider, and verify probe calibration before replacing parts."
                })

            # E. Ripple & Noise Evaluation (vpp evaluated independently of vave)
            if vpp > max_ripple * 2.5:
                health_score = max(15, health_score - 45)
                findings.append({
                    "level": "WARNING",
                    "title_ar": f"تموج وضوضاء كهربائية خطيرة ({vpp*1000:.1f} mVpp)",
                    "title_en": f"Severe Ripple / Noise ({vpp*1000:.1f} mVpp)",
                    "detail_ar": f"التموج المقاس {vpp*1000:.1f} mVpp يتجاوز الحد الأقصى المسموح ({max_ripple*1000:.1f} mVpp) بأكثر من 250%!",
                    "detail_en": f"Ripple noise {vpp*1000:.1f} mVpp severely exceeds max tolerance ({max_ripple*1000:.1f} mVpp)."
                })
                recommendations.append({
                    "step_ar": "احتمال مؤكد لجفاف أو تلف مكثفات التنعيم (Bad ESR Filter Capacitors) وفقدان سعتها التخزينية.",
                    "step_en": "High probability of degraded filter capacitors with high ESR. Replace bulk output capacitors."
                })
                recommendations.append({
                    "step_ar": "استبدل مكثف الخرج بآخر جديد من نوع منخفض المقاومة الداخلية (Low-ESR).",
                    "step_en": "Replace the output reservoir capacitor with a high-grade low-ESR unit."
                })
            elif vpp > max_ripple:
                health_score = max(55, health_score - 20)
                findings.append({
                    "level": "WARNING",
                    "title_ar": f"تموج تشويش مرتفع ({vpp*1000:.1f} mVpp)",
                    "title_en": f"Elevated Ripple ({vpp*1000:.1f} mVpp)",
                    "detail_ar": f"التموج المقاس {vpp*1000:.1f} mVpp أعلى من المعيار المثالي ({max_ripple*1000:.1f} mVpp).",
                    "detail_en": f"Ripple {vpp*1000:.1f} mVpp is elevated above threshold ({max_ripple*1000:.1f} mVpp)."
                })
                recommendations.append({
                    "step_ar": "أضف مكثف سيراميكي سعة 100nF بجانب أطراف تغذية الشريحة لامتصاص الترددات العالية.",
                    "step_en": "Add 100nF ceramic decoupling capacitor adjacent to IC power pins."
                })

            # F. Transient Overshoot Check (vmax vs DC nominal)
            # If vave is nominal, but vmax spikes: note as transient overshoot rather than fatal DC fault
            if min_allowed <= vave <= max_allowed and vmax > max_allowed * 1.12:
                health_score = max(60, health_score - 15)
                findings.append({
                    "level": "INFO",
                    "title_ar": f"رصد طفرات جهد عابرة (Overshoot Spikes: {vmax:.2f}V)",
                    "title_en": f"Transient Overshoot Spikes ({vmax:.2f}V peak)",
                    "detail_ar": f"متوسط الجهد مستقر ({vave:.2f}V) ولكن توجد قمم عابرة تصل إلى {vmax:.2f}V ناجمة عن رنين التبديل أو المحاثة.",
                    "detail_en": f"Average voltage is stable ({vave:.2f}V) but transient spikes reach {vmax:.2f}V (switching overshoot)."
                })
                recommendations.append({
                    "step_ar": "تحقق من شبكة الإخماد (Snubber Network) أو دايود الفريبوتش لمنع الرنين العابر.",
                    "step_en": "Inspect snubber network or freewheeling diode to damp transient ringing."
                })

            # G. Clean Nominal Rail
            if health_score >= 85 and len(findings) == 0:
                findings.append({
                    "level": "PASS",
                    "title_ar": "جهد التغذية مستقر ونظيف تماماً",
                    "title_en": "Power Rail Nominal And Clean",
                    "detail_ar": f"متوسط الجهد: {vave:.3f}V ضمن التسامح المقبول (±{tol_pct}%)، والتموج {vpp*1000:.1f} mVpp ممتاز.",
                    "detail_en": f"DC level {vave:.3f}V is nominal and ripple {vpp*1000:.1f} mVpp is pristine."
                })
                recommendations.append({
                    "step_ar": "خط التغذية في حالة ممتازة ولا يتطلب أي إجراء صيانة.",
                    "step_en": "Power rail is healthy. No maintenance required."
                })

        # ==========================================
        # 2. AC CLOCK & PWM SIGNALS
        # ==========================================
        elif p_type in ["AC_CLOCK", "PWM"]:
            min_amp = profile.get("min_amplitude_v", 0.5)
            if freq == 0 or vpp < 0.10:
                health_score = 0
                findings.append({
                    "level": "CRITICAL",
                    "title_ar": "إشارة متوقفة تماماً (Flatline / 0 Hz)",
                    "title_en": "Dead Clock / Flatline (0 Hz)",
                    "detail_ar": "لم يتم رصد أي تردد (0 Hz) أو نشاط نبضي. الكريستالة متوقفة أو المعالج في حالة تعليق كامل.",
                    "detail_en": "No clock oscillation or switching activity detected (0 Hz flatline)."
                })
                recommendations.append({
                    "step_ar": "تأكد من وصول جهد التغذية لآيسي المولد أو الميكروكنترولر.",
                    "step_en": "Ensure VDD supply is present at the clock source or microcontroller."
                })
                recommendations.append({
                    "step_ar": "افحص مكثفات تحميل الكريستالة (Load Capacitors 15-22pF) وافحص خط الـ RESET للتأكد من عدم تعليق المعالج.",
                    "step_en": "Inspect crystal load capacitors (15-22pF) and verify MCU RESET line is high."
                })
            elif vpp < min_amp:
                # Weak Amplitude Check (Reviewer Point 3 Fix)
                health_score = max(35, health_score - 50)
                findings.append({
                    "level": "WARNING",
                    "title_ar": f"اتساع الإشارة ضعيف وغير كافٍ ({vpp:.2f}V < {min_amp:.2f}V)",
                    "title_en": f"Weak Signal Amplitude ({vpp:.2f} Vpp < {min_amp:.2f} Vpp)",
                    "detail_ar": f"التذبذب موجود عند {freq:.1f} Hz ولكن اتساع القمة للقمة {vpp:.2f} Vpp أقل من الحد الأدنى المطلوب للمستويات المنطقية ({min_amp:.2f} Vpp).",
                    "detail_en": f"Oscillation active at {freq:.1f} Hz but amplitude {vpp:.2f} Vpp is below logic minimum ({min_amp:.2f} Vpp)."
                })
                recommendations.append({
                    "step_ar": "افحص مكثفات تحميل الكريستالة (15-22pF) ونظف أي أكسدة أو بقايا فلكس بين أرجل الكريستالة.",
                    "step_en": "Check crystal load capacitors (15-22pF) and clean flux residue between crystal pins."
                })
                recommendations.append({
                    "step_ar": "تحقق من سلامة مستوى جهد تغذية المذبذب (VDD) ومقاومة التغذية الراجعة الداخلية.",
                    "step_en": "Verify oscillator VDD supply level and feedback bias resistor."
                })
            else:
                findings.append({
                    "level": "PASS",
                    "title_ar": "نشاط التردد والنبض سليم ونشط",
                    "title_en": "Oscillation Active And Healthy",
                    "detail_ar": f"التردد المرصود: {freq:.2f} Hz ({freq/1000.0:.2f} kHz)، اتساع القمة للقمة: {vpp:.3f} Vpp.",
                    "detail_en": f"Oscillation active at {freq:.2f} Hz with {vpp:.3f} Vpp amplitude."
                })
                if p_type == "PWM":
                    findings.append({
                        "level": "INFO",
                        "title_ar": "نسبة دورة التشغيل (Duty Cycle)",
                        "title_en": "Duty Cycle Reading",
                        "detail_ar": f"دورة التشغيل الموجبة: +{duty_pos:.1f}% / السالبة: -{m.get('duty_neg_pct', 0):.1f}%.",
                        "detail_en": f"Positive Duty: +{duty_pos:.1f}% / Negative Duty: -{m.get('duty_neg_pct', 0):.1f}%."
                    })
                recommendations.append({
                    "step_ar": "المذبذب / مشغل النبضات يعمل بكفاءة.",
                    "step_en": "Clock generator / PWM driver is operating properly."
                })

        if unknown_profile_warning:
            findings.insert(0, {
                "level": "INFO",
                "title_ar": f"ملف اختبار غير معروف: '{profile_id}'",
                "title_en": f"Unknown Profile '{profile_id}'",
                "detail_ar": f"تم استخدام ملف خط التغذية 5.0V VCC القياسي تلقائياً لعدم تطابق اسم الملف.",
                "detail_en": f"Unknown profile ID '{profile_id}', defaulted to 5.0V VCC benchmark."
            })

        # Surface any field the driver had to clamp, so a reading is never
        # silently trusted when the instrument itself reported overflow.
        overflow_fields = m.get("overflow") or []
        if overflow_fields:
            voltage_overflow = any(str(f).startswith("v_") for f in overflow_fields)
            findings.insert(0, {
                # A clamped voltage invalidates the DC verdict itself, so it is a
                # warning; a clamped timing field is informational only.
                "level": "WARNING" if voltage_overflow else "INFO",
                "title_ar": "قراءات خارج مدى الجهاز (Overflow)",
                "title_en": "Instrument Overflow On Some Fields",
                "detail_ar": "الحقول التالية تجاوزت مدى القياس وتم قصرها عند الحد الأقصى، ولا يُعتمد عليها في هذا التشخيص: "
                             + "، ".join(str(x) for x in overflow_fields) + ".",
                "detail_en": "These fields exceeded the instrument range and were clamped; do not rely on them: "
                             + ", ".join(str(x) for x in overflow_fields) + "."
            })

        # ==========================================
        # 3. DERIVE SEVERITY & OVERALL TITLE (Issue 2 Fix)
        # ==========================================
        has_critical = any(f["level"] == "CRITICAL" for f in findings)
        has_warning = any(f["level"] == "WARNING" for f in findings)

        def _en_title(f: Dict[str, Any]) -> str:
            """English headline for a finding, never falling back to Arabic text."""
            title = f.get("title_en")
            if title:
                return title
            detail = (f.get("detail_en") or "").strip()
            if detail:
                return detail.split(". ")[0].strip().rstrip(".")
            return f.get("level", "Finding").title()

        if has_critical:
            severity = "CRITICAL"
            # Headline taken from the first critical finding
            crit_f = next(f for f in findings if f["level"] == "CRITICAL")
            status_title_ar = f"عطل حرج: {crit_f['title_ar']}"
            status_title_en = f"Critical Fault: {_en_title(crit_f)}"
        elif has_warning and health_score < 50:
            # No single fault is critical, but the accumulated defects are.
            # Do NOT label this "عطل حرج: انخفاض طفيف" - that contradicts itself.
            severity = "CRITICAL"
            warn_f = next(f for f in findings if f["level"] == "WARNING")
            status_title_ar = f"تدهور مركّب في النقطة (عدة عيوب مجتمعة): {warn_f['title_ar']}"
            status_title_en = f"Compound Degradation (multiple defects): {_en_title(warn_f)}"
        elif has_warning or health_score < 85:
            severity = "WARNING"
            # Headline taken from the first warning finding, if any
            warn_f = next((f for f in findings if f["level"] == "WARNING"), findings[0] if findings else None)
            if warn_f:
                status_title_ar = f"تنبيه: {warn_f['title_ar']}"
                status_title_en = f"Warning: {_en_title(warn_f)}"
            else:
                status_title_ar = "تنبيه: النقطة خارج الحالة المثالية"
                status_title_en = "Warning: measurement point is outside its ideal window"
        else:
            severity = "NORMAL"
            status_title_ar = "النقطة سليمة وتعمل ضمن المعايير القياسية"
            status_title_en = "Circuit rail is operating nominally within specs"

        return {
            "profile_id": profile["id"],
            "profile_name_ar": profile["name_ar"],
            "profile_name_en": profile["name_en"],
            "health_score": health_score,
            "severity": severity,
            "status_title_ar": status_title_ar,
            "status_title_en": status_title_en,
            "findings": findings,
            "recommendations": recommendations,
            "telemetry_snapshot": m
        }
