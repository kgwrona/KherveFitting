import wx

class LabelWindow(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Labels Manager")
        self.parent = parent
        self.SetSize((300, 300))

        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.WHITE)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.list_box = wx.ListBox(panel, style=wx.LB_SINGLE)
        sizer.Add(self.list_box, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(panel, label="Add")
        add_btn.SetMinSize((60, 40))
        edit_btn = wx.Button(panel, label="Edit")
        edit_btn.SetMinSize((60, 40))
        remove_btn = wx.Button(panel, label="Remove")
        remove_btn.SetMinSize((60, 40))

        btn_sizer.Add(add_btn, 0, wx.ALL, 5)
        btn_sizer.Add(edit_btn, 0, wx.ALL, 5)
        btn_sizer.Add(remove_btn, 0, wx.ALL, 5)

        add_btn.Bind(wx.EVT_BUTTON, self.on_add)
        edit_btn.Bind(wx.EVT_BUTTON, self.on_edit)
        remove_btn.Bind(wx.EVT_BUTTON, self.on_remove)

        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)
        panel.SetSizer(sizer)

        self.update_list()

    def update_list(self):
        self.list_box.Clear()
        sheet_name = self.parent.sheet_combobox.GetValue()
        if 'Labels' in self.parent.Data['Core levels'][sheet_name]:
            for label in self.parent.Data['Core levels'][sheet_name]['Labels']:
                self.list_box.Append(f"{label['text']} ({label['x']:.1f}, {label['y']:.1f})")

    def on_add(self, event):
        dlg = wx.TextEntryDialog(self, 'Enter text:', 'Add Text Annotation')
        if dlg.ShowModal() == wx.ID_OK:
            text = dlg.GetValue()
            sheet_name = self.parent.sheet_combobox.GetValue()
            maxY = max(self.parent.y_values)
            x = (self.parent.ax.get_xlim()[0] + self.parent.ax.get_xlim()[1]) / 2
            y = maxY * 1.1

            if 'Labels' not in self.parent.Data['Core levels'][sheet_name]:
                self.parent.Data['Core levels'][sheet_name]['Labels'] = []

            self.parent.Data['Core levels'][sheet_name]['Labels'].append({
                'text': text,
                'x': x,
                'y': y
            })

            # Clear all existing text annotations
            for txt in self.parent.ax.texts[:]:
                txt.remove()

            # Redraw all labels
            for label_data in self.parent.Data['Core levels'][sheet_name]['Labels']:
                self.parent.ax.text(
                    label_data['x'],
                    label_data['y'],
                    label_data['text'],
                    rotation=90,
                    va='bottom',
                    ha='center'
                )

            self.parent.canvas.draw_idle()
            self.update_list()
        dlg.Destroy()

    def on_edit(self, event):
        selection = self.list_box.GetSelection()
        if selection != wx.NOT_FOUND:
            sheet_name = self.parent.sheet_combobox.GetValue()
            label = self.parent.Data['Core levels'][sheet_name]['Labels'][selection]

            dlg = wx.Dialog(self, title="Edit Label", size=(250, 200))
            dlg.SetBackgroundColour(wx.WHITE)
            sizer = wx.BoxSizer(wx.VERTICAL)

            # Add text label and control
            text_sizer = wx.BoxSizer(wx.HORIZONTAL)
            text_label = wx.StaticText(dlg, label="Label:")
            text_ctrl = wx.TextCtrl(dlg, value=label['text'], size=(120, -1))
            text_sizer.Add(text_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
            text_sizer.Add(text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
            sizer.Add(text_sizer, 0, wx.EXPAND)

            # Add x control
            x_sizer = wx.BoxSizer(wx.HORIZONTAL)
            x_label = wx.StaticText(dlg, label="X:")
            x_ctrl = wx.SpinCtrlDouble(dlg, value=str(label['x']), min=-10, max=1e4, size=(120, -1))
            x_sizer.Add(x_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
            x_sizer.Add(x_ctrl, 1, wx.EXPAND | wx.ALL, 5)
            sizer.Add(x_sizer, 0, wx.EXPAND)

            # Add y control
            y_sizer = wx.BoxSizer(wx.HORIZONTAL)
            y_label = wx.StaticText(dlg, label="Y:")
            y_ctrl = wx.SpinCtrlDouble(dlg, value=str(label['y']), min=-10000, max=1e10, size=(120, -1))
            y_sizer.Add(y_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
            y_sizer.Add(y_ctrl, 1, wx.EXPAND | wx.ALL, 5)
            sizer.Add(y_sizer, 0, wx.EXPAND)

            # Add buttons
            btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
            ok_btn = wx.Button(dlg, wx.ID_OK, "OK", size=(60, 40))
            cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel", size=(60, 40))
            btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
            btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
            sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

            dlg.SetSizer(sizer)
            sizer.Fit(dlg)

            if dlg.ShowModal() == wx.ID_OK:
                label['text'] = text_ctrl.GetValue()
                label['x'] = x_ctrl.GetValue()
                label['y'] = y_ctrl.GetValue()

                # Clear all existing text annotations
                for txt in self.parent.ax.texts[:]:
                    txt.remove()

                # Redraw all labels
                for label_data in self.parent.Data['Core levels'][sheet_name]['Labels']:
                    self.parent.ax.text(
                        label_data['x'],
                        label_data['y'],
                        label_data['text'],
                        rotation=90,
                        va='bottom',
                        ha='center'
                    )

                self.parent.canvas.draw_idle()
                self.update_list()

            dlg.Destroy()

    def on_remove(self, event):
        selection = self.list_box.GetSelection()
        if selection != wx.NOT_FOUND:
            sheet_name = self.parent.sheet_combobox.GetValue()
            labels = self.parent.Data['Core levels'][sheet_name]['Labels']
            labels.pop(selection)

            # Clear all existing text annotations
            for text in self.parent.ax.texts[:]:
                text.remove()

            # Redraw remaining labels
            for label_data in labels:
                self.parent.ax.text(
                    label_data['x'],
                    label_data['y'],
                    label_data['text'],
                    rotation=90,
                    va='bottom',
                    ha='center'
                )

            self.parent.canvas.draw_idle()
            self.update_list()