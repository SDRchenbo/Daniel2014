import tkinter as tk
from tkinter import filedialog, messagebox
from td_steps_parser import parse_steps_for_action_id

class SimpleTDViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ATML TD 测试项目顺序号递归步骤调版")
        self.geometry("900x650")
        self.listbox = tk.Listbox(self, font=("微软雅黑", 13), width=38)
        self.listbox.pack(side=tk.LEFT, fill=tk.Y, expand=False)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        self.details = tk.Text(self, font=("微软雅黑", 14))
        self.details.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="打开ATML TD XML...", command=self.open_file)
        menubar.add_cascade(label="文件", menu=filemenu)
        self.config(menu=menubar)
        self.td_items = []
        self.action_id_map = []
        self.current_xml_file = None

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="请选择ATML TD XML文件",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        if not file_path:
            return
        self.current_xml_file = file_path

        # 基础：解析出测试项目、Action ID
        import xml.etree.ElementTree as ET
        def get_ns(root):
            if root.tag.startswith("{"):
                return root.tag.split("}")[0] + "}"
            return ""
        tree = ET.parse(file_path)
        root = tree.getroot()
        ns = get_ns(root)
        actions_dict = {}
        for act in root.findall(f".//{ns}Action"):
            aid = act.attrib.get("ID")
            if aid:
                actions_dict[aid] = act
        # 默认只取第一个TestGroup
        tg = root.find(f".//{ns}TestGroup")
        nodes = []
        action_ids = []
        # Initialization
        init_elem = tg.find(f".//{ns}InitializationAction")
        if init_elem is not None:
            aid = init_elem.attrib.get("actionID")
            nodes.append({'display': "[0] 测试建立", 'desc': "测试建立", 'aid': aid})
            action_ids.append(aid)
        # ActionReferences
        ar_nodes = []
        for ar in tg.findall(f"{ns}ActionReferences/{ns}ActionReference"):
            aid = ar.attrib.get('actionID')
            name = ""
            action = actions_dict.get(aid)
            if action is not None:
                name = action.attrib.get('name', '') or f"Action_{aid[:8]}"
            else:
                name = f"Action_{aid[:8]}"
            ar_nodes.append({'name': name, 'aid': aid})
        for idx, node in enumerate(ar_nodes, 1):
            nodes.append({'display': f"[{idx}] {node['name']}", 'desc': node['name'], 'aid': node['aid']})
            action_ids.append(node['aid'])
        # Termination
        term_elem = tg.find(f".//{ns}TerminationAction")
        if term_elem is not None:
            aid = term_elem.attrib.get("actionID")
            nodes.append({'display': "[99] 测试撤除", 'desc': "测试撤除", 'aid': aid})
            action_ids.append(aid)

        # 刷新界面
        self.td_items = nodes
        self.action_id_map = action_ids
        self.listbox.delete(0, tk.END)
        for node in self.td_items:
            self.listbox.insert(tk.END, node['display'])
        self.details.delete(1.0, tk.END)
        self.details.insert(tk.END, "请选择左侧测试步骤查看详情。")

    def on_select(self, event):
        idx = self.listbox.curselection()
        if not idx: return
        node = self.td_items[idx[0]]
        aid = node.get('aid', None)
        self.details.delete(1.0, tk.END)
        self.details.insert(tk.END, node['desc'] + "\n")
        if aid and self.current_xml_file:
            try:
                steps = parse_steps_for_action_id(self.current_xml_file, aid)
                if steps:
                    self.details.insert(tk.END, "\n".join(steps))
                else:
                    self.details.insert(tk.END, "\n(该测试项目下无详细步骤)")
            except Exception as e:
                self.details.insert(tk.END, f"\n(详细步骤提取出错: {e})")
        else:
            self.details.insert(tk.END, "\n(无步骤数据)")

if __name__ == "__main__":
    app = SimpleTDViewer()
    app.mainloop()