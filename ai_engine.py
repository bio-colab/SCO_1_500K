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
        """Runs thorough engineering rule-based and heuristics diagnostics on the measurements."""
        profile = dict(CIRCUIT_PROFILES.get(profile_id, CIRCUIT_PROFILES["5V_RAIL"]))
        if profile_id == "CUSTOM" and custom_params:
            profile["expected_v"] = float(custom_params.get("expected_v", 5.0))
            profile["tolerance_pct"] = float(custom_params.get("tolerance_pct", 5.0))
            profile["max_ripple_v"] = float(custom_params.get("max_ripple_v", 0.1))

        vmax = float(m.get("v_max", 0.0))
        vmin = float(m.get("v_min", 0.0))
        vave = float(m.get("v_ave", 0.0))
        vpp  = float(m.get("v_pp", 0.0))
        vrms = float(m.get("v_rms", 0.0))
        freq = float(m.get("frequency_hz", 0.0))
        period = float(m.get("period_us", 0.0))
        duty_pos = float(m.get("duty_pos_pct", 0.0))

        health_score = 100
        severity = "NORMAL"  # NORMAL, WARNING, CRITICAL
        findings = []
        recommendations = []
        status_title_ar = "النقطة سليمة وتعمل ضمن المعايير القياسية"
        status_title_en = "Circuit rail is operating nominally within specs"

        p_type = profile.get("type", "DC")

        if p_type == "DC":
            exp_v = profile["expected_v"]
            tol_pct = profile["tolerance_pct"]
            max_ripple = profile["max_ripple_v"]
            min_allowed = exp_v * (1.0 - tol_pct / 100.0)
            max_allowed = exp_v * (1.0 + tol_pct / 100.0)

            # 1. Dead Rail / Short Check
            if vmax < 0.25 and vave < 0.25:
                health_score = 0
                severity = "CRITICAL"
                status_title_ar = "خط التغذية ميت تماماً (0V) - شورت أو دائرة مفتوحة!"
                status_title_en = "Power rail is completely DEAD (0V) - Dead Short or Open Circuit!"
                findings.append({
                    "level": "CRITICAL",
                    "title_ar": "غياب تام للجهد (Dead Rail)",
                    "detail_ar": f"الجهد المقاس {vmax:.3f}V بينما المتوقع {exp_v:.2f}V. الخط لا يصله أي جهد إطلاقاً.",
                    "detail_en": f"Measured voltage {vmax:.3f}V while expecting {exp_v:.2f}V. Rail has 0V power."
                })
                recommendations.append({
                    "step_ar": "افصل التغذية فوراً وافحص المقاومة بين هذا الخط والأرضي (GND) بوضع الجرس/الدايود في الملتيميتر.",
                    "step_en": "Cut power and measure resistance from this rail to GND in diode/continuity mode."
                })
                recommendations.append({
                    "step_ar": "إذا رن الجرس (قريب من 0 أوم)، فهناك مكثف سيراميكي تالف (Shorted MLCC) أو آيسي محترق متصل بالخط.",
                    "step_en": "If it beeps (< 5 ohms), inspect ceramic filter capacitors (MLCC) or shorted ICs on this rail."
                })
                recommendations.append({
                    "step_ar": "إذا لم يكن هناك شورت، افحص فيوز الحماية (Fuse) أو منظم الجهد (Regulator) أو مفتاح التمكين (Enable Pin).",
                    "step_en": "If no short, verify input fuse, upstream regulator enable pin, or broken trace."
                })

            # 2. Severe Voltage Sag
            elif vmax < min_allowed * 0.85:
                health_score = max(10, health_score - 60)
                severity = "CRITICAL"
                status_title_ar = "هبوط حاد في الجهد (Severe Voltage Sag)"
                status_title_en = "Severe Voltage Sag Detected"
                findings.append({
                    "level": "CRITICAL",
                    "title_ar": "هبوط حاد جداً في الفولت",
                    "detail_ar": f"الجهد المقاس {vmax:.3f}V أقل بكثير من الحد الأدنى المسموح ({min_allowed:.2f}V).",
                    "detail_en": f"Voltage {vmax:.3f}V is severely below safe minimum threshold ({min_allowed:.2f}V)."
                })
                recommendations.append({
                    "step_ar": "تحقق من حرارة العناصر على هذا الخط بالكاميرا الحرارية أو اللمس؛ قد يكون هناك سحب تيار مفرط (Overload).",
                    "step_en": "Check component temperatures on this rail; excessive thermal output indicates overloaded regulator."
                })
                recommendations.append({
                    "step_ar": "افحص ملف الخرج (Inductor) ومكثفات التغذية لمنظم الخفض (Buck Converter).",
                    "step_en": "Inspect buck converter switching inductor and output filtering stage."
                })

            # 3. Moderate Sag
            elif vmax < min_allowed:
                health_score = max(50, health_score - 30)
                severity = "WARNING"
                status_title_ar = "انخفاض طفيف في الجهد تحت الحدود المسموحة"
                status_title_en = "Marginal Voltage Drop Detected"
                findings.append({
                    "level": "WARNING",
                    "title_ar": "انخفاض الجهد عن المعدل الطبيعي",
                    "detail_ar": f"الجهد المقاس {vmax:.3f}V (المتوقع {exp_v:.2f}V ±{tol_pct}%).",
                    "detail_en": f"Voltage {vmax:.3f}V is below nominal range {min_allowed:.2f}V - {max_allowed:.2f}V."
                })
                recommendations.append({
                    "step_ar": "تأكد من سلامة مقاومة مسار التغذية الراجعة (Feedback Resistors) للمنظم.",
                    "step_en": "Check feedback voltage divider network resistors around the voltage regulator."
                })

            # 4. Dangerous Overvoltage
            elif vmax > max_allowed:
                health_score = max(15, health_score - 70)
                severity = "CRITICAL"
                status_title_ar = "جهد زائد خطر (Over-Voltage Alert) - خطر احتراق الشرائح!"
                status_title_en = "Dangerous Overvoltage - High Risk of IC Destruction!"
                findings.append({
                    "level": "CRITICAL",
                    "title_ar": "ارتفاع خطر في الفولت",
                    "detail_ar": f"الجهد المقاس {vmax:.3f}V تجاوز الحد الأقصى الآمن ({max_allowed:.2f}V).",
                    "detail_en": f"Voltage {vmax:.3f}V exceeds safety upper limit ({max_allowed:.2f}V)."
                })
                recommendations.append({
                    "step_ar": "افصل الجهاز فوراً! منظم الجهد به عطل في حلقة التغذية أو شورت بين الدخل والخرج (Mosfet Punch-through).",
                    "step_en": "Power down immediately! Regulator high-side MOSFET may have punched through."
                })

            # 5. Ripple & Noise Check (Bad ESR Capacitors)
            if vpp > max_ripple * 2.5:
                health_score = max(20, health_score - 45)
                if severity == "NORMAL":
                    severity = "WARNING"
                findings.append({
                    "level": "WARNING",
                    "title_ar": "تموج وضوضاء كهربائية خطيرة (High Ripple)",
                    "detail_ar": f"قيمة التموج المقاسة {vpp*1000:.1f} mVpp أعلى بكثير من الحد الأقصى المقبول ({max_ripple*1000:.1f} mVpp).",
                    "detail_en": f"Ripple noise {vpp*1000:.1f} mVpp greatly exceeds maximum threshold ({max_ripple*1000:.1f} mVpp)."
                })
                recommendations.append({
                    "step_ar": "احتمال كبير جداً لتلف أو جفاف مكثفات التنعيم (Electrolytic / Polymer Capacitors) وارتفاع مقاومتها الداخلية (Bad ESR).",
                    "step_en": "High probability of dried-out filter capacitors with degraded ESR. Replace bulk capacitors."
                })
                recommendations.append({
                    "step_ar": "قم باستبدال مكثف التنعيم الملاصق لمنظم الجهد بآخر جديد منخفض الـ ESR (Low-ESR).",
                    "step_en": "Replace the output reservoir capacitor with a high-grade low-ESR unit."
                })
            elif vpp > max_ripple:
                health_score = max(60, health_score - 20)
                if severity == "NORMAL":
                    severity = "WARNING"
                findings.append({
                    "level": "INFO",
                    "title_ar": "تموج تشويش خفيف في الخط",
                    "detail_ar": f"التموج المقاس {vpp*1000:.1f} mVpp أعلى بقليل من المعيار المثالي ({max_ripple*1000:.1f} mVpp).",
                    "detail_en": f"Ripple {vpp*1000:.1f} mVpp is slightly elevated."
                })
                recommendations.append({
                    "step_ar": "أضف مكثف سيراميكي سعة 100nF بجانب آيسي الحمل لامتصاص الضوضاء عالية التردد.",
                    "step_en": "Add 100nF ceramic decoupling capacitor adjacent to load ICs."
                })

            # If all passed
            if health_score >= 85 and len(findings) == 0:
                findings.append({
                    "level": "PASS",
                    "title_ar": "الجهد الاسمي مستقر ونظيف تماماً",
                    "detail_ar": f"الجهد: {vmax:.3f}V ضمن التسامح المقبول (±{tol_pct}%)، والتموج {vpp*1000:.1f} mVpp في الحدود الممتازة.",
                    "detail_en": f"Voltage {vmax:.3f}V is nominal and ripple {vpp*1000:.1f} mVpp is pristine."
                })
                recommendations.append({
                    "step_ar": "خط التغذية في حالة صحية مثالية ولا يحتاج لأي صيانة.",
                    "step_en": "Power rail is healthy. No maintenance required."
                })

        elif p_type in ["AC_CLOCK", "PWM"]:
            min_amp = profile.get("min_amplitude_v", 0.5)
            if freq == 0 or vpp < 0.15:
                health_score = 0
                severity = "CRITICAL"
                status_title_ar = "إشارة الساعة / النبضات متوقفة تماماً (Flatline / Dead Clock)!"
                status_title_en = "Clock or PWM signal is completely flatline (0 Hz)!"
                findings.append({
                    "level": "CRITICAL",
                    "title_ar": "غياب التردد والنبضات",
                    "detail_ar": "لم يتم رصد أي تردد (0 Hz) أو اتساع إشارة متناوبة.",
                    "detail_en": "No clock oscillation or switching activity detected."
                })
                recommendations.append({
                    "step_ar": "تأكد من وصول جهد التغذية لآيسي المولد أو الميكروكنترولر.",
                    "step_en": "Ensure VDD supply is present at the clock source or microcontroller."
                })
                recommendations.append({
                    "step_ar": "افحص مكثفات تحميل الكريستالة (Load Capacitors 15-22pF) وافحص خط الـ RESET للتأكد من عدم تعليق المعالج.",
                    "step_en": "Inspect crystal load capacitors (15-22pF) and verify MCU RESET line is high."
                })
            else:
                findings.append({
                    "level": "PASS",
                    "title_ar": "نشاط التردد والنبض سليم ونشط",
                    "detail_ar": f"التردد المرصود: {freq:.2f} Hz ({freq/1000.0:.2f} kHz)، اتساع القمة للقمة: {vpp:.3f} Vpp.",
                    "detail_en": f"Oscillation active at {freq:.2f} Hz with {vpp:.3f} Vpp amplitude."
                })
                if p_type == "PWM":
                    findings.append({
                        "level": "INFO",
                        "title_ar": "نسبة دورة التشغيل (Duty Cycle)",
                        "detail_ar": f"دورة التشغيل الموجبة: +{duty_pos:.1f}% / السالبة: -{m.get('duty_neg_pct', 0):.1f}%.",
                        "detail_en": f"Positive Duty: +{duty_pos:.1f}% / Negative Duty: -{m.get('duty_neg_pct', 0):.1f}%."
                    })
                recommendations.append({
                    "step_ar": "المذبذب / مشغل النبضات يعمل بكفاءة.",
                    "step_en": "Clock generator / PWM driver is operating properly."
                })

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
