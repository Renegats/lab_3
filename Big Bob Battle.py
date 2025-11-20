import random
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import List, Dict, Any, Tuple
import json
import os
from datetime import datetime


class Attack:
    def __init__(self, name: str, attack_bonus: int, damage_dice_count: int,
                 damage_dice_type: str, damage_modifier: int, damage_type: str = ""):
        self.name = name
        self.attack_bonus = attack_bonus
        self.damage_dice_count = damage_dice_count
        self.damage_dice_type = damage_dice_type
        self.damage_modifier = damage_modifier
        self.damage_type = damage_type

    def to_dict(self):
        return {
            'name': self.name,
            'attack_bonus': self.attack_bonus,
            'damage_dice_count': self.damage_dice_count,
            'damage_dice_type': self.damage_dice_type,
            'damage_modifier': self.damage_modifier,
            'damage_type': self.damage_type
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data['name'],
            data['attack_bonus'],
            data['damage_dice_count'],
            data['damage_dice_type'],
            data['damage_modifier'],
            data.get('damage_type', '')
        )


class Enemy:
    def __init__(self, name: str, hp: int, ac: int, attacks: List[Attack], side: int):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.ac = ac
        self.attacks = attacks
        self.side = side
        self.alive = True
        self.ignore_sides = set()

    def take_damage(self, damage: int):
        # Урон не может быть отрицательным
        actual_damage = max(0, damage)
        self.hp -= actual_damage
        if self.hp <= 0:
            self.alive = False
            self.hp = 0
        return self.alive

    def perform_attack(self, attack: Attack, target_ac: int) -> Tuple[bool, int, int, bool, str]:
        attack_roll = random.randint(1, 20)
        total_attack = attack_roll + attack.attack_bonus
        critical = (attack_roll == 20)
        hit = total_attack >= target_ac or critical

        damage_info = ""
        if hit:
            # Calculate damage
            dice_type = int(attack.damage_dice_type.split('d')[1])
            damage = sum(random.randint(1, dice_type) for _ in range(attack.damage_dice_count)) + attack.damage_modifier

            # Double damage on critical hit
            if critical:
                damage *= 2

            # Урон не может быть отрицательным
            damage = max(0, damage)

            damage_info = f"{damage} урона"
            if attack.damage_type:
                damage_info += f" ({attack.damage_type})"

            return True, damage, total_attack, critical, damage_info
        return False, 0, total_attack, critical, damage_info

    def to_dict(self):
        return {
            'name': self.name,
            'max_hp': self.max_hp,
            'hp': self.hp,
            'ac': self.ac,
            'attacks': [attack.to_dict() for attack in self.attacks],
            'side': self.side,
            'alive': self.alive,
            'ignore_sides': list(self.ignore_sides)
        }

    @classmethod
    def from_dict(cls, data):
        enemy = cls(
            data['name'],
            data['max_hp'],
            data['ac'],
            [Attack.from_dict(attack_data) for attack_data in data['attacks']],
            data['side']
        )
        enemy.hp = data['hp']
        enemy.alive = data['alive']
        enemy.ignore_sides = set(data['ignore_sides'])
        return enemy


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        self.canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # Bind mouse wheel scrolling
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.scrollable_frame.bind("<MouseWheel>", self._on_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class BattleSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Мастер Подземелий - Симулятор Битв")
        self.root.geometry("1600x900")

        self.sides = []  # List of lists of enemies for each side
        self.num_sides = 2
        self.side_names = ["Сторона А", "Сторона Б", "Сторона В", "Сторона Г", "Сторона Д", "Сторона Е"]
        self.alliance_settings = []  # Для сохранения настроек альянсов

        self.setup_ui()

    def setup_ui(self):
        # Main notebook
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Setup tab
        setup_frame = ttk.Frame(notebook)
        notebook.add(setup_frame, text="Настройка армий")

        # Create scrollable frame for setup
        setup_scroll_frame = ScrollableFrame(setup_frame)
        setup_scroll_frame.pack(fill='both', expand=True)

        # Save/Load buttons
        file_frame = ttk.Frame(setup_scroll_frame.scrollable_frame)
        file_frame.pack(fill='x', pady=10)

        ttk.Button(file_frame, text="Сохранить настройки", command=self.save_settings).pack(side='left', padx=5)
        ttk.Button(file_frame, text="Загрузить настройки", command=self.load_settings).pack(side='left', padx=5)

        # Number of sides
        ttk.Label(setup_scroll_frame.scrollable_frame, text="Количество сторон:", font=('Arial', 10, 'bold')).pack(
            anchor='w', pady=10)
        side_frame = ttk.Frame(setup_scroll_frame.scrollable_frame)
        side_frame.pack(fill='x', pady=5)

        self.num_sides_var = tk.IntVar(value=2)
        ttk.Spinbox(side_frame, from_=2, to=6, textvariable=self.num_sides_var, width=10,
                    command=self.update_sides_ui).pack(side='left')

        # Side setup frames
        self.side_frames = []
        self.side_count_vars = []
        self.side_name_vars = []

        sides_container = ttk.Frame(setup_scroll_frame.scrollable_frame)
        sides_container.pack(fill='x', pady=10)

        for i in range(6):
            frame = ttk.LabelFrame(sides_container, text=f"Сторона {chr(65 + i)}")
            frame.grid(row=i // 3, column=i % 3, padx=5, pady=5, sticky='ew')
            self.side_frames.append(frame)

            # Side name
            ttk.Label(frame, text="Название стороны:").grid(row=0, column=0, sticky='w')
            name_var = tk.StringVar(value=f"Сторона {chr(65 + i)}")
            ttk.Entry(frame, textvariable=name_var, width=15).grid(row=0, column=1, padx=5)
            self.side_name_vars.append(name_var)

            # Enemy count
            ttk.Label(frame, text="Количество врагов:").grid(row=1, column=0, sticky='w', pady=5)
            count_var = tk.IntVar(value=5 if i < 2 else 0)
            ttk.Spinbox(frame, from_=0, to=100, textvariable=count_var, width=10).grid(row=1, column=1, padx=5, pady=5)
            self.side_count_vars.append(count_var)

            frame.grid_remove()  # Hide initially

        # Configure sides container grid
        for i in range(3):
            sides_container.grid_columnconfigure(i, weight=1)

        # Common settings
        ttk.Label(setup_scroll_frame.scrollable_frame, text="=== Общие настройки ===", font=('Arial', 12, 'bold')).pack(
            anchor='w', pady=10)

        common_frame = ttk.Frame(setup_scroll_frame.scrollable_frame)
        common_frame.pack(fill='x', pady=5)

        # Left column
        left_frame = ttk.Frame(common_frame)
        left_frame.grid(row=0, column=0, padx=10, sticky='nw')

        ttk.Label(left_frame, text="Класс доспеха:").grid(row=0, column=0, sticky='w', pady=5)
        self.armor_class = ttk.Spinbox(left_frame, from_=1, to=30, width=10)
        self.armor_class.set("10")
        self.armor_class.grid(row=0, column=1, pady=5)

        ttk.Label(left_frame, text="Здоровье:").grid(row=1, column=0, sticky='w', pady=5)
        self.health = ttk.Spinbox(left_frame, from_=1, to=500, width=10)
        self.health.set("10")
        self.health.grid(row=1, column=1, pady=5)

        # Right column - default attack settings
        right_frame = ttk.Frame(common_frame)
        right_frame.grid(row=0, column=1, padx=10, sticky='nw')

        ttk.Label(right_frame, text="Базовая атака:", font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2,
                                                                                       sticky='w', pady=5)

        ttk.Label(right_frame, text="Название атаки:").grid(row=1, column=0, sticky='w', pady=2)
        self.attack_name = ttk.Entry(right_frame, width=15)
        self.attack_name.insert(0, "Атака")
        self.attack_name.grid(row=1, column=1, pady=2)

        ttk.Label(right_frame, text="Бонус к атаке:").grid(row=2, column=0, sticky='w', pady=2)
        self.attack_bonus = ttk.Spinbox(right_frame, from_=-10, to=20, width=10)
        self.attack_bonus.set("0")
        self.attack_bonus.grid(row=2, column=1, pady=2)

        ttk.Label(right_frame, text="Кол-во костей:").grid(row=3, column=0, sticky='w', pady=2)
        self.damage_dice_count = ttk.Spinbox(right_frame, from_=1, to=20, width=10)
        self.damage_dice_count.set("1")
        self.damage_dice_count.grid(row=3, column=1, pady=2)

        ttk.Label(right_frame, text="Тип кости:").grid(row=4, column=0, sticky='w', pady=2)
        self.damage_dice_type = ttk.Combobox(right_frame, values=["d4", "d6", "d8", "d10", "d12"], width=10)
        self.damage_dice_type.set("d6")
        self.damage_dice_type.grid(row=4, column=1, pady=2)

        ttk.Label(right_frame, text="Модификатор:").grid(row=5, column=0, sticky='w', pady=2)
        self.damage_modifier = ttk.Spinbox(right_frame, from_=-10, to=20, width=10)
        self.damage_modifier.set("0")
        self.damage_modifier.grid(row=5, column=1, pady=2)

        ttk.Label(right_frame, text="Тип урона:").grid(row=6, column=0, sticky='w', pady=2)
        self.damage_type = ttk.Entry(right_frame, width=15)
        self.damage_type.grid(row=6, column=1, pady=2)

        common_frame.grid_columnconfigure(0, weight=1)
        common_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(setup_scroll_frame.scrollable_frame, text="Создать армии", command=self.create_armies).pack(pady=20)

        # Battle tab
        self.battle_frame = ttk.Frame(notebook)
        notebook.add(self.battle_frame, text="Битва")

        # Configure battle frame grid
        self.battle_frame.grid_rowconfigure(0, weight=1)
        self.battle_frame.grid_rowconfigure(1, weight=0)

        # Alliance tab
        self.alliance_frame = ttk.Frame(notebook)
        notebook.add(self.alliance_frame, text="Альянсы")

        # Initial UI update
        self.update_sides_ui()

    def update_sides_ui(self):
        num_sides = self.num_sides_var.get()

        for i in range(6):
            if i < num_sides:
                self.side_frames[i].grid()
            else:
                self.side_frames[i].grid_remove()

    def save_settings(self):
        try:
            # Create settings directory if it doesn't exist
            if not os.path.exists('battle_settings'):
                os.makedirs('battle_settings')

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"battle_settings/battle_{timestamp}.json"

            # Сохраняем текущие настройки альянсов
            current_alliance_settings = []
            if hasattr(self, 'alliance_vars'):
                for i in range(len(self.alliance_vars)):
                    row_settings = []
                    for j in range(len(self.alliance_vars[i])):
                        if self.alliance_vars[i][j] is not None:
                            row_settings.append(self.alliance_vars[i][j].get())
                        else:
                            row_settings.append(False)
                    current_alliance_settings.append(row_settings)

            settings = {
                'num_sides': self.num_sides_var.get(),
                'side_names': [var.get() for var in self.side_name_vars],
                'side_counts': [var.get() for var in self.side_count_vars],
                'armor_class': int(self.armor_class.get()),
                'health': int(self.health.get()),
                'attack_name': self.attack_name.get(),
                'attack_bonus': int(self.attack_bonus.get()),
                'damage_dice_count': int(self.damage_dice_count.get()),
                'damage_dice_type': self.damage_dice_type.get(),
                'damage_modifier': int(self.damage_modifier.get()),
                'damage_type': self.damage_type.get(),
                'alliance_settings': current_alliance_settings if current_alliance_settings else self.alliance_settings
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)

            messagebox.showinfo("Успех", f"Настройки сохранены в файл:\n{filename}")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при сохранении: {str(e)}")

    def load_settings(self):
        try:
            filename = filedialog.askopenfilename(
                title="Выберите файл настроек",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir="battle_settings"
            )

            if not filename:
                return

            with open(filename, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            # Apply settings
            self.num_sides_var.set(settings['num_sides'])
            self.update_sides_ui()

            for i in range(6):
                if i < len(settings['side_names']):
                    self.side_name_vars[i].set(settings['side_names'][i])
                    self.side_count_vars[i].set(settings['side_counts'][i])

            self.armor_class.set(settings['armor_class'])
            self.health.set(settings['health'])
            self.attack_name.delete(0, tk.END)
            self.attack_name.insert(0, settings['attack_name'])
            self.attack_bonus.set(settings['attack_bonus'])
            self.damage_dice_count.set(settings['damage_dice_count'])
            self.damage_dice_type.set(settings['damage_dice_type'])
            self.damage_modifier.set(settings['damage_modifier'])
            self.damage_type.delete(0, tk.END)
            self.damage_type.insert(0, settings.get('damage_type', ''))

            # Load alliance settings if they exist
            if 'alliance_settings' in settings:
                self.alliance_settings = settings['alliance_settings']

            messagebox.showinfo("Успех", "Настройки загружены!")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при загрузке: {str(e)}")

    def create_armies(self):
        try:
            num_sides = self.num_sides_var.get()
            self.num_sides = num_sides

            ac = int(self.armor_class.get())
            hp = int(self.health.get())

            # Create default attack
            default_attack = Attack(
                self.attack_name.get(),
                int(self.attack_bonus.get()),
                int(self.damage_dice_count.get()),
                self.damage_dice_type.get(),
                int(self.damage_modifier.get()),
                self.damage_type.get()
            )

            self.sides = []
            self.side_names = []

            # Create enemies for each side
            for i in range(num_sides):
                side_name = self.side_name_vars[i].get()
                enemy_count = self.side_count_vars[i].get()
                self.side_names.append(side_name)

                side_enemies = []
                for j in range(enemy_count):
                    name = f"{side_name}_{j + 1}"
                    enemy = Enemy(name, hp, ac, [default_attack], i)
                    side_enemies.append(enemy)

                self.sides.append(side_enemies)

            # Удаляем ссылку на текстовое поле перед созданием нового UI
            if hasattr(self, 'battle_results_text'):
                delattr(self, 'battle_results_text')

            self.setup_battle_ui()
            self.setup_alliance_ui()

            messagebox.showinfo("Успех", f"Армии созданы!\nКоличество сторон: {num_sides}")

        except ValueError:
            messagebox.showerror("Ошибка", "Пожалуйста, введите корректные значения!")

    def setup_alliance_ui(self):
        # Clear alliance frame
        for widget in self.alliance_frame.winfo_children():
            widget.destroy()

        if self.num_sides <= 2:
            ttk.Label(self.alliance_frame, text="Для настройки альянсов требуется минимум 3 стороны",
                      font=('Arial', 12)).pack(pady=50)
            return

        # Create scrollable frame for alliances
        alliance_scroll_frame = ScrollableFrame(self.alliance_frame)
        alliance_scroll_frame.pack(fill='both', expand=True)

        ttk.Label(alliance_scroll_frame.scrollable_frame,
                  text="Настройка альянсов - выберите, какие стороны игнорируют друг друга",
                  font=('Arial', 12, 'bold')).pack(pady=10)

        # Create alliance matrix
        alliance_frame = ttk.Frame(alliance_scroll_frame.scrollable_frame)
        alliance_frame.pack(pady=20)

        # Header row
        for i in range(self.num_sides):
            ttk.Label(alliance_frame, text=self.side_names[i], font=('Arial', 10, 'bold')).grid(row=0, column=i + 1,
                                                                                                padx=10, pady=5)

        # Alliance matrix
        self.alliance_vars = []
        for i in range(self.num_sides):
            row_vars = []
            ttk.Label(alliance_frame, text=self.side_names[i], font=('Arial', 10, 'bold')).grid(row=i + 1, column=0,
                                                                                                padx=10, pady=5)

            for j in range(self.num_sides):
                if i == j:
                    ttk.Label(alliance_frame, text="-").grid(row=i + 1, column=j + 1, padx=5, pady=2)
                    row_vars.append(None)
                else:
                    var = tk.BooleanVar()
                    # Restore previous alliance settings if they exist
                    if hasattr(self, 'alliance_settings') and self.alliance_settings:
                        if i < len(self.alliance_settings) and j < len(self.alliance_settings[i]):
                            var.set(self.alliance_settings[i][j])
                    cb = ttk.Checkbutton(alliance_frame, variable=var)
                    cb.grid(row=i + 1, column=j + 1, padx=5, pady=2)
                    row_vars.append(var)

            self.alliance_vars.append(row_vars)

        ttk.Button(alliance_scroll_frame.scrollable_frame, text="Применить настройки альянсов",
                   command=self.apply_alliances).pack(pady=20)

    def apply_alliances(self):
        # Save alliance settings
        self.alliance_settings = []
        for i in range(self.num_sides):
            row_settings = []
            for j in range(self.num_sides):
                if i == j:
                    row_settings.append(False)
                else:
                    row_settings.append(self.alliance_vars[i][j].get())
            self.alliance_settings.append(row_settings)

        # Reset all ignore lists first
        for side in self.sides:
            for enemy in side:
                enemy.ignore_sides.clear()

        # Apply new alliances
        for i in range(self.num_sides):
            for j in range(self.num_sides):
                if i != j and self.alliance_vars[i][j] and self.alliance_vars[i][j].get():
                    # Add j to ignore list for side i
                    for enemy in self.sides[i]:
                        enemy.ignore_sides.add(j)

        messagebox.showinfo("Успех", "Настройки альянсов применены!")

    def setup_battle_ui(self):
        # Полностью очищаем battle frame
        for widget in self.battle_frame.winfo_children():
            widget.destroy()

        # Создаем основной контейнер с прокруткой
        main_scroll_frame = ScrollableFrame(self.battle_frame)
        main_scroll_frame.pack(fill='both', expand=True)

        # Create frames for each side with scrollbars
        self.side_vars = []
        self.side_frames_battle = []

        enemy_frames_container = ttk.Frame(main_scroll_frame.scrollable_frame)
        enemy_frames_container.pack(fill='x', pady=(0, 10))

        # Calculate number of columns based on number of sides
        num_columns = min(self.num_sides, 3)  # Max 3 columns

        for i, (side_enemies, side_name) in enumerate(zip(self.sides, self.side_names)):
            side_container = ttk.LabelFrame(enemy_frames_container, text=side_name)
            side_container.grid(row=i // num_columns, column=i % num_columns, padx=5, pady=5, sticky='nsew')

            # Create scrollable frame
            scroll_frame = ScrollableFrame(side_container)
            scroll_frame.pack(fill='both', expand=True)

            side_vars = []
            select_all_var = tk.BooleanVar()

            # Select all checkbox
            select_frame = ttk.Frame(scroll_frame.scrollable_frame)
            select_frame.pack(fill='x', pady=5)
            ttk.Checkbutton(select_frame, text="Выделить все", variable=select_all_var,
                            command=lambda idx=i: self.toggle_select_all(idx)).pack(side='left')

            for j, enemy in enumerate(side_enemies):
                var = tk.BooleanVar()
                frame = ttk.Frame(scroll_frame.scrollable_frame)
                frame.pack(fill='x', pady=2)

                ttk.Checkbutton(frame, variable=var).pack(side='left')
                status = "🟢" if enemy.alive else "🔴"

                # Display enemy info with attacks
                attack_info = ", ".join([f"{attack.name}+{attack.attack_bonus}" for attack in enemy.attacks])
                ttk.Label(frame, text=f"{status} {enemy.name}: {enemy.hp}/{enemy.max_hp} HP [{attack_info}]").pack(
                    side='left')

                ttk.Button(frame, text="Изменить",
                           command=lambda e=enemy: self.edit_enemy(e)).pack(side='right')
                side_vars.append(var)

            self.side_vars.append(side_vars)
            self.side_frames_battle.append((scroll_frame, select_all_var))

        # Configure enemy frames container grid
        for i in range(num_columns):
            enemy_frames_container.grid_columnconfigure(i, weight=1)

        # Results section
        results_label = ttk.Label(main_scroll_frame.scrollable_frame, text="Результаты боя:",
                                  font=('Arial', 10, 'bold'))
        results_label.pack(anchor='w', pady=(10, 5))

        # Create results text widget with scrollbar
        results_container = ttk.Frame(main_scroll_frame.scrollable_frame)
        results_container.pack(fill='both', expand=True, pady=(0, 10))

        self.battle_results_text = tk.Text(results_container, height=15, width=100)
        results_scrollbar = ttk.Scrollbar(results_container, orient="vertical", command=self.battle_results_text.yview)

        self.battle_results_text.configure(yscrollcommand=results_scrollbar.set)
        self.battle_results_text.pack(side='left', fill='both', expand=True)
        results_scrollbar.pack(side='right', fill='y')

        # Battle controls
        controls_frame = ttk.Frame(self.battle_frame)
        controls_frame.pack(fill='x', pady=10)

        # Center the buttons
        button_container = ttk.Frame(controls_frame)
        button_container.pack(expand=True)

        ttk.Button(button_container, text="Провести раунд боя", command=self.run_battle_round).pack(side='left', padx=5)
        ttk.Button(button_container, text="Массовое редактирование", command=self.mass_edit).pack(side='left', padx=5)
        ttk.Button(button_container, text="Показать статус", command=self.show_status).pack(side='left', padx=5)
        ttk.Button(button_container, text="Очистить результаты", command=self.clear_results).pack(side='left', padx=5)

    def clear_results(self):
        if hasattr(self, 'battle_results_text'):
            self.battle_results_text.delete(1.0, tk.END)

    def toggle_select_all(self, side_idx):
        select_all_var = self.side_frames_battle[side_idx][1]
        for var in self.side_vars[side_idx]:
            var.set(select_all_var.get())

    def mass_edit(self):
        selected_enemies = []

        for i, side_vars in enumerate(self.side_vars):
            for j, var in enumerate(side_vars):
                if var.get():
                    selected_enemies.append(self.sides[i][j])

        if not selected_enemies:
            messagebox.showwarning("Внимание", "Выберите хотя бы одного врага для редактирования!")
            return

        # Open mass edit dialog
        self.open_mass_edit_dialog(selected_enemies)

    def open_mass_edit_dialog(self, enemies):
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Массовое редактирование")
        edit_window.geometry("600x800")
        edit_window.minsize(600, 700)

        # Create scrollable frame for the dialog
        main_frame = ttk.Frame(edit_window)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Bind mouse wheel scrolling
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        scrollable_frame.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side='right', fill='y')

        ttk.Label(scrollable_frame, text=f"Редактирование {len(enemies)} врагов",
                  font=('Arial', 12, 'bold')).pack(pady=10)

        # Basic info
        ttk.Label(scrollable_frame, text="Основные параметры:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)

        ttk.Label(scrollable_frame, text="Имя:").pack(anchor='w', pady=2)
        name_var = tk.StringVar(value=enemies[0].name)
        ttk.Entry(scrollable_frame, textvariable=name_var, width=30).pack(pady=2)

        ttk.Label(scrollable_frame, text="Здоровье:").pack(anchor='w', pady=2)
        hp_var = tk.IntVar(value=enemies[0].hp)
        ttk.Spinbox(scrollable_frame, from_=1, to=500, textvariable=hp_var, width=10).pack(pady=2)

        ttk.Label(scrollable_frame, text="Класс доспеха:").pack(anchor='w', pady=2)
        ac_var = tk.IntVar(value=enemies[0].ac)
        ttk.Spinbox(scrollable_frame, from_=1, to=30, textvariable=ac_var, width=10).pack(pady=2)

        # Attacks section
        ttk.Label(scrollable_frame, text="Атаки:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))

        # Frame for attacks list
        attacks_frame = ttk.Frame(scrollable_frame)
        attacks_frame.pack(fill='x', pady=5)

        # Listbox for attacks
        ttk.Label(attacks_frame, text="Список атак:").pack(anchor='w')
        attacks_listbox = tk.Listbox(attacks_frame, height=4)
        attacks_listbox.pack(fill='x', pady=5)

        # Buttons for managing attacks
        attack_buttons_frame = ttk.Frame(attacks_frame)
        attack_buttons_frame.pack(fill='x', pady=5)

        ttk.Button(attack_buttons_frame, text="Добавить атаку",
                   command=lambda: self.add_attack_to_listbox(attacks_listbox, enemies[0])).pack(side='left', padx=2)
        ttk.Button(attack_buttons_frame, text="Удалить атаку",
                   command=lambda: self.remove_attack_from_listbox(attacks_listbox, enemies[0])).pack(side='left',
                                                                                                      padx=2)
        ttk.Button(attack_buttons_frame, text="Редактировать атаку",
                   command=lambda: self.edit_attack_in_listbox(attacks_listbox, enemies[0])).pack(side='left', padx=2)

        # Attack details frame (initially hidden)
        attack_details_frame = ttk.Frame(scrollable_frame)

        # Populate attacks listbox
        self.update_attacks_listbox(attacks_listbox, enemies[0])

        def save_changes():
            for enemy in enemies:
                enemy.name = name_var.get()
                enemy.hp = hp_var.get()
                enemy.max_hp = hp_var.get()
                enemy.ac = ac_var.get()
                enemy.alive = enemy.hp > 0

            edit_window.destroy()
            self.setup_battle_ui()
            messagebox.showinfo("Успех", f"Параметры {len(enemies)} врагов обновлены!")

        # Save button at the bottom
        ttk.Button(scrollable_frame, text="Сохранить", command=save_changes).pack(pady=20)

        # Store references for access in methods
        self.current_edit_enemies = enemies
        self.current_attacks_listbox = attacks_listbox
        self.current_attack_details_frame = attack_details_frame

    def update_attacks_listbox(self, listbox, enemy):
        listbox.delete(0, tk.END)
        for attack in enemy.attacks:
            listbox.insert(tk.END,
                           f"{attack.name} (+{attack.attack_bonus}, {attack.damage_dice_count}{attack.damage_dice_type}+{attack.damage_modifier})")

    def add_attack_to_listbox(self, listbox, enemy):
        # Create a new attack dialog
        attack_dialog = tk.Toplevel(self.root)
        attack_dialog.title("Добавить атаку")
        attack_dialog.geometry("400x500")

        ttk.Label(attack_dialog, text="Новая атака", font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(attack_dialog, text="Название атаки:").pack(pady=2)
        name_var = tk.StringVar(value="Новая атака")
        ttk.Entry(attack_dialog, textvariable=name_var, width=30).pack(pady=2)

        ttk.Label(attack_dialog, text="Бонус к атаке:").pack(pady=2)
        bonus_var = tk.IntVar(value=0)
        ttk.Spinbox(attack_dialog, from_=-10, to=20, textvariable=bonus_var, width=10).pack(pady=2)

        ttk.Label(attack_dialog, text="Кол-во костей:").pack(pady=2)
        dice_count_var = tk.IntVar(value=1)
        ttk.Spinbox(attack_dialog, from_=1, to=20, textvariable=dice_count_var, width=10).pack(pady=2)

        ttk.Label(attack_dialog, text="Тип кости:").pack(pady=2)
        dice_type_var = tk.StringVar(value="d6")
        ttk.Combobox(attack_dialog, values=["d4", "d6", "d8", "d10", "d12"],
                     textvariable=dice_type_var, width=10).pack(pady=2)

        ttk.Label(attack_dialog, text="Модификатор:").pack(pady=2)
        mod_var = tk.IntVar(value=0)
        ttk.Spinbox(attack_dialog, from_=-10, to=20, textvariable=mod_var, width=10).pack(pady=2)

        ttk.Label(attack_dialog, text="Тип урона:").pack(pady=2)
        damage_type_var = tk.StringVar(value="")
        ttk.Entry(attack_dialog, textvariable=damage_type_var, width=20).pack(pady=2)

        def add_attack():
            new_attack = Attack(
                name_var.get(),
                bonus_var.get(),
                dice_count_var.get(),
                dice_type_var.get(),
                mod_var.get(),
                damage_type_var.get()
            )
            enemy.attacks.append(new_attack)
            self.update_attacks_listbox(listbox, enemy)
            attack_dialog.destroy()

        ttk.Button(attack_dialog, text="Добавить", command=add_attack).pack(pady=20)

    def remove_attack_from_listbox(self, listbox, enemy):
        selection = listbox.curselection()
        if selection:
            index = selection[0]
            enemy.attacks.pop(index)
            self.update_attacks_listbox(listbox, enemy)
        else:
            messagebox.showwarning("Внимание", "Выберите атаку для удаления!")

    def edit_attack_in_listbox(self, listbox, enemy):
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите атаку для редактирования!")
            return

        index = selection[0]
        attack = enemy.attacks[index]

        # Create edit attack dialog
        attack_dialog = tk.Toplevel(self.root)
        attack_dialog.title("Редактировать атаку")
        attack_dialog.geometry("400x500")

        ttk.Label(attack_dialog, text="Редактирование атаки", font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(attack_dialog, text="Название атаки:").pack(pady=2)
        name_var = tk.StringVar(value=attack.name)
        ttk.Entry(attack_dialog, textvariable=name_var, width=30).pack(pady=2)

        ttk.Label(attack_dialog, text="Бонус к атаке:").pack(pady=2)
        bonus_var = tk.IntVar(value=attack.attack_bonus)
        ttk.Spinbox(attack_dialog, from_=-10, to=20, textvariable=bonus_var, width=10).pack(pady=2)

        ttk.Label(attack_dialog, text="Кол-во костей:").pack(pady=2)
        dice_count_var = tk.IntVar(value=attack.damage_dice_count)
        ttk.Spinbox(attack_dialog, from_=1, to=20, textvariable=dice_count_var, width=10).pack(pady=2)

        ttk.Label(attack_dialog, text="Тип кости:").pack(pady=2)
        dice_type_var = tk.StringVar(value=attack.damage_dice_type)
        ttk.Combobox(attack_dialog, values=["d4", "d6", "d8", "d10", "d12"],
                     textvariable=dice_type_var, width=10).pack(pady=2)

        ttk.Label(attack_dialog, text="Модификатор:").pack(pady=2)
        mod_var = tk.IntVar(value=attack.damage_modifier)
        ttk.Spinbox(attack_dialog, from_=-10, to=20, textvariable=mod_var, width=10).pack(pady=2)

        ttk.Label(attack_dialog, text="Тип урона:").pack(pady=2)
        damage_type_var = tk.StringVar(value=attack.damage_type)
        ttk.Entry(attack_dialog, textvariable=damage_type_var, width=20).pack(pady=2)

        def save_attack():
            attack.name = name_var.get()
            attack.attack_bonus = bonus_var.get()
            attack.damage_dice_count = dice_count_var.get()
            attack.damage_dice_type = dice_type_var.get()
            attack.damage_modifier = mod_var.get()
            attack.damage_type = damage_type_var.get()

            self.update_attacks_listbox(listbox, enemy)
            attack_dialog.destroy()

        ttk.Button(attack_dialog, text="Сохранить", command=save_attack).pack(pady=20)

    def edit_enemy(self, enemy):
        self.open_mass_edit_dialog([enemy])

    def show_status(self):
        status_text = "=== ТЕКУЩИЙ СТАТУС ===\n\n"

        for i, (side_enemies, side_name) in enumerate(zip(self.sides, self.side_names)):
            status_text += f"{side_name}:\n"
            for enemy in side_enemies:
                status = "🟢 ЖИВ" if enemy.alive else "🔴 МЕРТВ"
                ignore_text = f" (Игнорирует: {', '.join([self.side_names[s] for s in enemy.ignore_sides])})" if enemy.ignore_sides else ""
                attacks_text = ", ".join([f"{attack.name}+{attack.attack_bonus}" for attack in enemy.attacks])
                status_text += f"  {enemy.name}: {enemy.hp}/{enemy.max_hp} HP [{attacks_text}] ({status}){ignore_text}\n"
            status_text += "\n"

        if hasattr(self, 'battle_results_text'):
            self.battle_results_text.insert(tk.END, status_text + "\n")
            self.battle_results_text.see(tk.END)

    def run_battle_round(self):
        if not self.sides or not any(any(enemy.alive for enemy in side) for side in self.sides):
            messagebox.showerror("Ошибка", "Армии не созданы или все мертвы!")
            return

        battle_log = "=== НОВЫЙ РАУНД БОЯ ===\n\n"

        # Process attacks for each side
        for attacker_side_idx, side_enemies in enumerate(self.sides):
            alive_attackers = [e for e in side_enemies if e.alive]

            for attacker in alive_attackers:
                # Find potential targets (alive enemies from other sides that aren't ignored)
                potential_targets = []
                for target_side_idx, target_side in enumerate(self.sides):
                    if (target_side_idx != attacker_side_idx and
                            target_side_idx not in attacker.ignore_sides):
                        alive_targets = [e for e in target_side if e.alive]
                        potential_targets.extend(alive_targets)

                if not potential_targets:
                    battle_log += f"{attacker.name} - нет подходящих целей для атаки\n"
                    continue

                target = random.choice(potential_targets)

                # Perform all attacks for this enemy
                for attack in attacker.attacks:
                    hit, damage, attack_roll, critical, damage_info = attacker.perform_attack(attack, target.ac)

                    if hit:
                        target.take_damage(damage)
                        crit_text = " КРИТИЧЕСКИЙ УДАР!" if critical else ""
                        battle_log += f"{attacker.name} → {target.name} ({attack.name}: {attack_roll} vs AC {target.ac}) - ПОПАДАНИЕ!{crit_text} {damage_info}\n"
                        if not target.alive:
                            battle_log += f"☠️ {target.name} УНИЧТОЖЕН!\n"
                            break  # Stop attacking if target is dead
                    else:
                        battle_log += f"{attacker.name} → {target.name} ({attack.name}: {attack_roll} vs AC {target.ac}) - ПРОМАХ!\n"

            battle_log += "\n"

        # Check battle outcome
        alive_sides = []
        for i, side_enemies in enumerate(self.sides):
            if any(enemy.alive for enemy in side_enemies):
                alive_sides.append(self.side_names[i])

        if len(alive_sides) <= 1:
            if alive_sides:
                battle_log += f"\n🎉 {alive_sides[0]} ПОБЕДИЛА!\n"
            else:
                battle_log += "\n⚔️ Все стороны уничтожены! Ничья.\n"
        else:
            battle_log += f"\nБитва продолжается: {' vs '.join(alive_sides)}\n"

        # Вставляем результаты в текстовое поле
        if hasattr(self, 'battle_results_text'):
            self.battle_results_text.insert(tk.END, battle_log + "\n")
        self.battle_results_text.see(tk.END)

        # Обновляем UI чтобы показать изменения в здоровье
        self.update_battle_ui()

    def update_battle_ui(self):
        # Обновляем только отображение здоровья без полного пересоздания UI
        for i, (side_enemies, side_vars) in enumerate(zip(self.sides, self.side_vars)):
            for j, (enemy, var) in enumerate(zip(side_enemies, side_vars)):
                # Находим соответствующий фрейм врага
                scroll_frame, _ = self.side_frames_battle[i]
                # +1 потому что первый child - это "Выделить все"
                if j + 1 < len(scroll_frame.scrollable_frame.winfo_children()):
                    enemy_frame = scroll_frame.scrollable_frame.winfo_children()[j + 1]

                    # Находим label с здоровьем (второй дочерний элемент фрейма)
                    if len(enemy_frame.winfo_children()) > 1:
                        health_label = enemy_frame.winfo_children()[1]
                        status = "🟢" if enemy.alive else "🔴"
                        attack_info = ", ".join([f"{attack.name}+{attack.attack_bonus}" for attack in enemy.attacks])
                        health_label.configure(
                            text=f"{status} {enemy.name}: {enemy.hp}/{enemy.max_hp} HP [{attack_info}]")


def main():
    root = tk.Tk()
    app = BattleSimulator(root)
    root.mainloop()


if __name__ == "__main__":
    main()