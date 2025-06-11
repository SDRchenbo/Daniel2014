import xml.etree.ElementTree as ET

def get_ns(root):
    if root.tag.startswith("{"):
        return root.tag.split("}")[0] + "}"
    return ""

def clean(t):
    return "" if t is None else str(t).replace("\n", "").replace("\r", "").strip()

def extract_ports_from_signal(sig, ns):
    for tw_tag in ["TwoWire", "TwoWireComp"]:
        tw = sig.find(f"{ns}{tw_tag}") or sig.find(".//{*}" + tw_tag)
        if tw is not None:
            hi = tw.attrib.get("hi") or tw.attrib.get("true") or ""
            lo = tw.attrib.get("lo") or tw.attrib.get("comp") or ""
            if hi or lo:
                return f"{hi} ↔ {lo}"
    ports = []
    for port in sig.findall(".//{*}Port"):
        pname = port.attrib.get("name", "")
        if pname:
            ports.append(pname)
    return "，".join(ports)

def parse_operations(operations_elem, ns, step_prefix="", level=1, step_counter=[1]):
    result = []
    if operations_elem is None:
        return ["(无详细测试步骤或Operations节点缺失)"]
    op_map = {
        "OperationConnect": "连接",
        "OperationShort": "短接",
        "OperationDisconnect": "断开",
        "OperationSetup": "建立",
        "OperationRead": "读取",
        "OperationSetValue": "赋值",
        "OperationCalculate": "计算",
        "OperationWaitFor": "延时",
        "OperationDelay": "延时",
        "OperationRepeat": "循环",
        "OperationReset": "复位",
        "OperationConditional": "条件",
    }
    for op in operations_elem:
        if not op.tag.endswith('Operation'):
            continue
        name = op.attrib.get('name', '')
        xsi_type = op.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}type', '')
        op_type = xsi_type.split(':')[-1] if xsi_type else op.tag.split('}')[-1]
        cname = op_map.get(op_type, op_type)
        step_num = f"{step_prefix}{step_counter[0]}"
        detail = f"步骤{step_num}：{cname}"
        subinfo = []

        if op_type == "OperationSetup":
            sensor = op.find(f"{ns}Sensor") or op.find(".//{*}Sensor")
            sig_name = ""
            port_txt = ""
            if sensor is not None:
                lsr = sensor.find(f"{ns}LocalSensorSignalReference") or sensor.find(".//{*}LocalSensorSignalReference")
                if lsr is not None:
                    sig_name = lsr.attrib.get('localSensorSignalID', '') or lsr.attrib.get('localSignalID', '')
                signal = sensor.find(f"{ns}Signal") or sensor.find(".//{*}Signal")
                if signal is not None:
                    port_txt = extract_ports_from_signal(signal, ns)
            if sig_name:
                subinfo.append(f"信号: {sig_name}")
            if port_txt:
                subinfo.append(f"端口: {port_txt}")
        elif op_type in ["OperationConnect", "OperationDisconnect"]:
            sig = op.find(f"{ns}Signal") or op.find(".//{*}Signal")
            sig_name = ""
            port_txt = ""
            if sig is not None:
                lsr = sig.find(f"{ns}LocalSignalReference") or sig.find(".//{*}LocalSignalReference")
                if lsr is not None:
                    sig_name = lsr.attrib.get('localSignalID', '')
                port_txt = extract_ports_from_signal(sig, ns)
            if sig_name:
                subinfo.append(f"信号: {sig_name}")
            if port_txt:
                subinfo.append(f"端口: {port_txt}")
        elif op_type == "OperationRead":
            local_sensor = op.find(f"{ns}LocalSensorSignalReference") or op.find(".//{*}LocalSensorSignalReference")
            sig_name = ""
            if local_sensor is not None:
                sig_name = local_sensor.attrib.get('localSensorSignalID', '') or local_sensor.attrib.get('localSignalID', '')
            outvalues = op.find(f"{ns}OutValues") or op.find(".//{*}OutValues")
            vars_txt = []
            if outvalues is not None:
                for outv in outvalues:
                    pname = outv.attrib.get("parameterDescriptionName", "")
                    if pname:
                        vars_txt.append(pname)
            if sig_name:
                subinfo.append(f"信号: {sig_name}")
            if vars_txt:
                subinfo.append(f"变量: {', '.join(vars_txt)}")
        elif op_type == "OperationSetValue":
            outvar = op.find(f"{ns}OutputResult") or op.find(".//{*}OutputResult")
            vname = outvar.attrib.get("referenceName", "") if outvar is not None else ""
            if vname:
                subinfo.append(f"输出变量: {vname}")
        elif op_type == "OperationCalculate":
            exp = op.find(f"{ns}Expression") or op.find(".//{*}Expression")
            outvar = op.find(f"{ns}OutputResult") or op.find(".//{*}OutputResult")
            vname = outvar.attrib.get("referenceName", "") if outvar is not None else ""
            etxt = exp.text.strip() if exp is not None and exp.text else ""
            subinfo.append(f"{etxt}")
            if vname:
                subinfo.append(f"输出变量: {vname}")
        elif op_type in ["OperationWaitFor", "OperationDelay"]:
            tval = op.find(f"{ns}TimeValue") or op.find(".//{*}TimeValue")
            if tval is not None and tval.attrib.get("value"):
                subinfo.append(f"延时: {tval.attrib.get('value', '')}ms")
            else:
                timeout = op.find(f"{ns}Timeout") or op.find(".//{*}Timeout")
                if timeout is not None and timeout.text:
                    subinfo.append(f"延时: {timeout.text.strip()}")
        elif op_type == "OperationRepeat":
            detail += "（循环体）"
            body = op.find(f"{ns}Body") or op.find(".//{*}Body")
            if body is not None:
                substeps = parse_operations(body, ns, step_prefix=f"{step_num}.", level=level+1, step_counter=[1])
                result.append(detail)
                result += substeps
                step_counter[0] += 1
                continue
        elif op_type == "OperationReset":
            local = op.find(f"{ns}LocalSignalReference") or op.find(".//{*}LocalSignalReference")
            sig_name = ""
            if local is not None:
                sig_name = local.attrib.get('localSignalID', '')
            if sig_name:
                subinfo.append(f"信号: {sig_name}")
        elif op_type == "OperationShort":
            # 针对短接（也可能含端口/信号）
            interface = op.find(f"{ns}Interface") or op.find(".//{*}Interface")
            if interface is not None:
                network = interface.find(f"{ns}Network") or interface.find(".//{*}Network")
                ports = []
                if network is not None:
                    for node in network.findall(f".//{ns}Node") + network.findall(".//{*}Node"):
                        path = node.find(f"{ns}Path") or node.find(".//{*}Path")
                        if path is not None and path.text:
                            ports.append(path.text.split("@name='")[-1].split("']")[0])
                if ports:
                    subinfo.append("端口: " + " ↔ ".join(ports))
        elif op_type == "OperationConditional":
            detail += "（条件体）"
            decision = op.find(f"{ns}Decision") or op.find(".//{*}Decision")
            if decision is not None:
                # OnTrue
                ontrue = op.find(f"{ns}OnTrue") or op.find(".//{*}OnTrue")
                if ontrue is not None:
                    true_steps = parse_operations(ontrue, ns, step_prefix=f"{step_num}.T", level=level+1, step_counter=[1])
                    result.append(detail + " [满足条件]")
                    result += true_steps
                # OnFalse
                onfalse = op.find(f"{ns}OnFalse") or op.find(".//{*}OnFalse")
                if onfalse is not None:
                    false_steps = parse_operations(onfalse, ns, step_prefix=f"{step_num}.F", level=level+1, step_counter=[1])
                    result.append(detail + " [不满足条件]")
                    result += false_steps
                step_counter[0] += 1
                continue
        info = "  ".join(subinfo)
        result.append(f"{detail}  {info}".rstrip())
        step_counter[0] += 1
    return result

def extract_limits_and_target(testresult_elem, ns):
    target = ""
    limits = []
    nom = testresult_elem.find(f".//{ns}Nominal") or testresult_elem.find(".//{*}Nominal")
    if nom is not None:
        target = nom.find(f".//{ns}Datum") or nom.find(".//{*}Datum")
        if target is not None:
            target = target.attrib.get("value", "")
    for lim in testresult_elem.findall(f".//{ns}LimitPair") + testresult_elem.findall(".//{*}LimitPair"):
        lower = lim.find(f"{ns}Limit[@comparator='GE']") or lim.find(".//{*}Limit[@comparator='GE']")
        upper = lim.find(f"{ns}Limit[@comparator='LE']") or lim.find(".//{*}Limit[@comparator='LE']")
        lval = ""
        uval = ""
        if lower is not None:
            ldatum = lower.find(f"{ns}Datum") or lower.find(".//{*}Datum")
            if ldatum is not None:
                lval = ldatum.attrib.get("value", "")
        if upper is not None:
            udatum = upper.find(f"{ns}Datum") or upper.find(".//{*}Datum")
            if udatum is not None:
                uval = udatum.attrib.get("value", "")
        if lval or uval:
            limits.append((lval, uval))
    return target, limits

def get_action_ids_from_testgroup(root, ns, testgroup_id):
    tg = root.find(f".//{{*}}TestGroup[@ID='{testgroup_id}']")
    action_ids = []
    if tg is not None:
        for actref in tg.findall(".//{*}ActionReference"):
            action_ids.append(actref.attrib["actionID"])
    return action_ids

def get_steps_from_actions(root, ns, action_ids):
    steps = []
    for aid in action_ids:
        action = root.find(f".//{{*}}Action[@ID='{aid}']")
        if action is not None:
            # 找到Behavior->Operations，调用你已有的parse_operations
            behavior = action.find(f"{ns}Behavior") or action.find(".//{*}Behavior")
            if behavior is not None:
                operations = behavior.find(f"{ns}Operations") or behavior.find(".//{*}Operations")
                if operations is not None:
                    steps += parse_operations(operations, ns)
                else:
                    steps.append(f"(未找到Operations节点, ActionID={aid})")
            else:
                steps.append(f"(未找到Behavior节点, ActionID={aid})")
            # 判据
            testresults = action.find(f"{ns}TestResults") or action.find(".//{*}TestResults")
            if testresults is not None:
                for testresult in testresults.findall(f"{ns}TestResult") + testresults.findall(".//{*}TestResult"):
                    tname = testresult.attrib.get("name", "")
                    target, limits = extract_limits_and_target(testresult, ns)
                    if tname and (target or limits):
                        limit_txt = ""
                        if limits:
                            limit_txt = f"判定范围：{limits[0][0]} ≤ 实测 ≤ {limits[0][1]}"
                        steps.append(f"步骤判定：目标: {tname} {limit_txt}")
    return steps

def parse_steps_for_action_id(xml_path, testgroup_id):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = get_ns(root)
        action_ids = get_action_ids_from_testgroup(root, ns, testgroup_id)
        if not action_ids:
            return [f"(未找到TestGroup或ActionReference，TestGroupID={testgroup_id})"]
        steps = get_steps_from_actions(root, ns, action_ids)
        return steps
    except Exception as e:
        return [f"(详细步骤提取出错: {e})"]

if __name__ == "__main__":
    xml_path = "多模接收机GLU-920_TD.xml"
    # 替换为你要解析的TestGroup的ID
    testgroup_id = "dd2917dd-a4d2-4f1c-b6d8-85476dc97a95"  # VOLT_MON.BLK
    steps = extract_steps_by_testgroup_id(xml_path, testgroup_id)
    for s in steps:
        print(s)