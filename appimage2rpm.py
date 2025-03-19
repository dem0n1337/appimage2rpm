#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import logging
import tempfile
import shutil
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QFileDialog, QProgressBar, 
    QMessageBox, QGroupBox, QFormLayout, QTextEdit, QCheckBox,
    QTabWidget, QComboBox, QSpinBox, QListWidget, QListWidgetItem,
    QRadioButton, QButtonGroup, QDialog, QDialogButtonBox, QInputDialog
)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize

from appimage_utils import AppImageExtractor
from rpm_utils import RPMBuilder
from dependency_utils import DependencyAnalyzer, DistroProfileManager
from repo_utils import RepoManager

# Nastavenie loggeru
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AppImage2RPM")

class ConversionThread(QThread):
    """Vlákno pre konverziu AppImage na RPM"""
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str, str)
    
    def __init__(self, appimage_path, output_dir, metadata=None, distro_profile=None, auto_deps=True, parent=None, repo_info=None):
        super().__init__(parent)
        self.appimage_path = appimage_path
        self.output_dir = output_dir
        self.metadata = metadata or {}
        self.distro_profile = distro_profile
        self.auto_deps = auto_deps
        self.repo_info = repo_info
        
    def run(self):
        try:
            # Aktualizácia stavu
            self.progress_signal.emit(5, "Inicializácia...")
            
            # Inicializácia profile manažéra
            profile_manager = DistroProfileManager()
            if not self.distro_profile:
                # Ak nie je špecifikovaný profil, použiť aktuálnu distribúciu
                self.distro_profile = profile_manager.detect_current_distro()
                
            profile = profile_manager.get_profile(self.distro_profile)
            if not profile:
                self.progress_signal.emit(0, f"Nepodporovaný profil distribúcie: {self.distro_profile}")
                self.finished_signal.emit(False, "", f"Nepodporovaný profil distribúcie: {self.distro_profile}")
                return
                
            self.progress_signal.emit(10, f"Používam profil: {profile['name']}")
            
            # Vytvorenie RPM makier pre danú distribúciu
            macros_file = profile_manager.create_rpm_macros(self.distro_profile)
            if macros_file:
                self.progress_signal.emit(15, f"Vytvorené RPM makrá pre {profile['name']}")
            
            # Extrakcia AppImage
            self.progress_signal.emit(20, "Extrakcia AppImage...")
            extractor = AppImageExtractor(self.appimage_path)
            extracted_dir = extractor.extract()
            
            self.progress_signal.emit(30, "Získavanie metadát...")
            
            # Získanie metadát
            if not self.metadata:
                metadata = extractor.parse_metadata()
            else:
                metadata = self.metadata
                
            # Pokročilá detekcia závislostí
            requires = []
            if self.auto_deps:
                self.progress_signal.emit(35, "Detekcia závislostí...")
                analyzer = DependencyAnalyzer(extracted_dir)
                analyzer.analyze_dependencies()
                
                # Získanie závislostí pre danú distribúciu
                distro_id = profile["id"]  # fedora, rhel, centos
                requires = analyzer.convert_dependencies_to_rpm_requires(distro_id)
                
                if requires:
                    self.progress_signal.emit(40, f"Detekovaných {len(requires)} závislostí")
                    # Pridanie závislostí do metadát
                    metadata["requires"] = requires
                else:
                    self.progress_signal.emit(40, "Žiadne závislosti neboli detekované")
            
            # Získanie ikony
            self.progress_signal.emit(45, "Hľadanie ikony...")
            icon_path = extractor.get_icon_file()
            
            self.progress_signal.emit(50, "Príprava RPM balíka...")
            
            # Vytvorenie RPM balíka
            builder = RPMBuilder(
                app_name=metadata.get('name', ''),
                app_version=metadata.get('version', '1.0.0'),
                extracted_dir=extracted_dir,
                icon_path=icon_path  # RPMBuilder automaticky nájde ikonu, ak je icon_path None
            )
            
            # Ak bola ikona automaticky nájdená, vypíšeme ju do logu
            if builder.icon_path and not icon_path:
                logger.info(f"Automaticky nájdená ikona: {builder.icon_path}")
                self.progress_signal.emit(55, f"Automaticky nájdená ikona v AppImage")
            elif builder.icon_path:
                logger.info(f"Používam ikonu: {builder.icon_path}")
                self.progress_signal.emit(55, f"Ikona nájdená: {os.path.basename(str(builder.icon_path))}")
            else:
                logger.warning("Nebola nájdená žiadna ikona")
                self.progress_signal.emit(55, "Nebola nájdená žiadna ikona")
            
            self.progress_signal.emit(70, "Zostavenie RPM balíka...")
            
            # Zostavenie RPM
            rpm_file = builder.build_rpm(
                output_dir=self.output_dir,
                requires=metadata.get('requires', []),
                description=metadata.get('description', ''),
                license=metadata.get('license', 'Unspecified'),
                summary=metadata.get('description', ''),
                url=metadata.get('homepage', ''),
                categories=metadata.get('categories', [])
            )
            
            # Publikovanie do repozitára
            if self.repo_info and rpm_file:
                self.progress_signal.emit(80, "Publikovanie do repozitára...")
                
                repo_type = self.repo_info.get("type")
                repo_name = self.repo_info.get("name")
                
                # Inicializácia správcu repozitárov
                repo_manager = RepoManager()
                
                # Publikovanie RPM do repozitára
                success = repo_manager.publish_rpm(
                    rpm_path=rpm_file,
                    pkg_name=metadata.get('name', ''),
                    repo_name=repo_name
                )
                
                if success:
                    self.progress_signal.emit(85, "RPM balík bol úspešne publikovaný do repozitára")
                    
                    # Uloženie konfigurácie repozitára
                    repo_config_file = repo_manager.save_repo_config(repo_type, repo_name)
                    if repo_config_file:
                        self.progress_signal.emit(90, f"Konfigurácia repozitára uložená: {repo_config_file}")
                else:
                    self.progress_signal.emit(85, "Chyba pri publikovaní do repozitára")
            else:
                self.progress_signal.emit(85, "Preskakujem publikovanie do repozitára")
            
            self.progress_signal.emit(95, "Čistenie dočasných súborov...")
            
            # Vyčistenie dočasných súborov
            extractor.cleanup()
            builder.cleanup()
            
            self.progress_signal.emit(100, "Konverzia dokončená!")
            
            # Signál o úspešnom dokončení
            if rpm_file:
                self.finished_signal.emit(True, str(rpm_file), "Konverzia bola úspešná!")
            else:
                self.finished_signal.emit(False, "", "Nepodarilo sa vytvoriť RPM balík.")
                
        except Exception as e:
            logger.error(f"Chyba pri konverzii: {e}", exc_info=True)
            self.finished_signal.emit(False, "", f"Chyba pri konverzii: {str(e)}")

class DistroProfileWidget(QWidget):
    """Widget pre správu a výber profilov distribúcií"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.profile_manager = DistroProfileManager()
        self.current_profile = self.profile_manager.detect_current_distro()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Skupina pre výber distribúcie
        profile_group = QGroupBox("Profil distribúcie")
        profile_layout = QVBoxLayout()
        
        # Profil selector
        self.profile_combo = QComboBox()
        self.reload_profiles()
        profile_layout.addWidget(QLabel("Vyberte profil distribúcie:"))
        profile_layout.addWidget(self.profile_combo)
        
        # Detaily profilu
        details_group = QGroupBox("Detaily profilu")
        self.details_layout = QFormLayout()
        
        self.profile_name_label = QLabel("")
        self.profile_id_label = QLabel("")
        self.profile_version_label = QLabel("")
        
        self.details_layout.addRow("Názov:", self.profile_name_label)
        self.details_layout.addRow("ID:", self.profile_id_label)
        self.details_layout.addRow("Verzia:", self.profile_version_label)
        
        details_group.setLayout(self.details_layout)
        
        # Pripojenie signálu pre zmenu profilu
        self.profile_combo.currentIndexChanged.connect(self.update_profile_details)
        
        profile_layout.addWidget(details_group)
        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)
        
        # Tlačidlá
        buttons_layout = QHBoxLayout()
        self.detect_button = QPushButton("Autodetekcia distribúcie")
        self.detect_button.clicked.connect(self.detect_distribution)
        
        buttons_layout.addWidget(self.detect_button)
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Aktualizácia detailov pre aktuálny profil
        self.update_profile_details()
        
    def reload_profiles(self):
        """Načíta profily distribúcií do comboboxu"""
        self.profile_combo.clear()
        
        profiles = self.profile_manager.get_all_profiles()
        for profile_id, profile in profiles.items():
            self.profile_combo.addItem(profile["name"], profile_id)
            
        # Nastavenie aktuálneho profilu
        for i in range(self.profile_combo.count()):
            if self.profile_combo.itemData(i) == self.current_profile:
                self.profile_combo.setCurrentIndex(i)
                break
                
    def update_profile_details(self):
        """Aktualizuje detaily pre vybraný profil"""
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return
            
        self.current_profile = profile_id
        profile = self.profile_manager.get_profile(profile_id)
        
        if profile:
            self.profile_name_label.setText(profile["name"])
            self.profile_id_label.setText(profile["id"])
            self.profile_version_label.setText(profile["version"])
            
    def detect_distribution(self):
        """Autodetekcia aktuálnej distribúcie"""
        detected_profile = self.profile_manager.detect_current_distro()
        
        if detected_profile:
            self.current_profile = detected_profile
            
            # Nastavenie detekovaného profilu v comboboxe
            for i in range(self.profile_combo.count()):
                if self.profile_combo.itemData(i) == detected_profile:
                    self.profile_combo.setCurrentIndex(i)
                    break
                    
            QMessageBox.information(
                self,
                "Autodetekcia distribúcie",
                f"Detekovaná distribúcia: {self.profile_manager.get_profile(detected_profile)['name']}"
            )
            
    def get_current_profile(self):
        """Vráti ID aktuálne vybraného profilu"""
        return self.current_profile


class RepoManagerWidget(QWidget):
    """Widget pre správu repozitárov"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo_manager = RepoManager()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Vytvorenie repozitára
        create_group = QGroupBox("Vytvorenie repozitára")
        create_layout = QVBoxLayout()
        
        # Výber typu repozitára
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Typ repozitára:"))
        
        self.repo_type_combo = QComboBox()
        
        # Načítanie dostupných profilov
        profiles = self.repo_manager.get_available_profiles()
        for profile in profiles:
            info = self.repo_manager.get_profile_info(profile)
            if info:
                self.repo_type_combo.addItem(info.get("name", profile), profile)
                
        type_layout.addWidget(self.repo_type_combo)
        create_layout.addLayout(type_layout)
        
        # Názov repozitára
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Názov repozitára:"))
        
        self.repo_name_edit = QLineEdit()
        self.repo_name_edit.setPlaceholderText("napr. my-appimages")
        
        name_layout.addWidget(self.repo_name_edit)
        create_layout.addLayout(name_layout)
        
        # Vytvorenie repozitára
        buttons_layout = QHBoxLayout()
        
        self.create_repo_button = QPushButton("Vytvoriť repozitár")
        self.create_repo_button.clicked.connect(self.create_repository)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.create_repo_button)
        
        create_layout.addLayout(buttons_layout)
        create_group.setLayout(create_layout)
        layout.addWidget(create_group)
        
        # Konfigurácia repozitára
        config_group = QGroupBox("Konfigurácia repozitára")
        config_layout = QVBoxLayout()
        
        self.config_text = QTextEdit()
        self.config_text.setReadOnly(True)
        self.config_text.setPlaceholderText("Tu sa zobrazí konfigurácia po vytvorení repozitára")
        
        # Info o COPR autentifikácii
        self.auth_info_label = QLabel()
        self.auth_info_label.setWordWrap(True)
        self.auth_info_label.setStyleSheet("color: #CC0000; font-style: italic;")
        self.auth_info_label.setText(
            "Poznámka: Pre COPR repozitáre potrebujete vytvorit konfiguračný súbor ~/.config/copr s API tokenom.\n"
            "Tokeny môžete získať na https://copr.fedorainfracloud.org/api po prihlásení."
        )
        
        # Vytvorenie pomocnej konfigurácie pre COPR
        self.setup_copr_button = QPushButton("Nastaviť COPR autentifikáciu...")
        self.setup_copr_button.clicked.connect(self.setup_copr_auth)
        
        config_layout.addWidget(self.config_text)
        config_layout.addWidget(self.auth_info_label)
        config_layout.addWidget(self.setup_copr_button)
        
        # Tlačidlo na uloženie konfigurácie
        save_layout = QHBoxLayout()
        
        self.save_config_button = QPushButton("Uložiť konfiguráciu...")
        self.save_config_button.clicked.connect(self.save_config)
        self.save_config_button.setEnabled(False)
        
        save_layout.addStretch()
        save_layout.addWidget(self.save_config_button)
        
        config_layout.addLayout(save_layout)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        self.setLayout(layout)
        
    def create_repository(self):
        """Vytvorí nový repozitár"""
        repo_type = self.repo_type_combo.currentData()
        repo_name = self.repo_name_edit.text()
        
        if not repo_name:
            QMessageBox.warning(self, "Chyba", "Zadajte názov repozitára")
            return
            
        try:
            # Vytvorenie repozitára
            success = self.repo_manager.create_repo(profile_name=repo_type, repo_name=repo_name)
            
            if success:
                QMessageBox.information(
                    self,
                    "Repozitár vytvorený",
                    f"Repozitár {repo_name} bol úspešne vytvorený"
                )
                
                # Aktualizácia konfigurácie
                config = self.repo_manager.generate_repo_config(repo_type=repo_type, repo_name=repo_name)
                self.config_text.setText(config)
                self.save_config_button.setEnabled(True)
            else:
                QMessageBox.critical(
                    self,
                    "Chyba",
                    f"Chyba pri vytváraní repozitára {repo_name}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Chyba",
                f"Chyba pri vytváraní repozitára: {str(e)}"
            )
            
    def save_config(self):
        """Uloží konfiguráciu repozitára do súboru"""
        repo_type = self.repo_type_combo.currentData()
        repo_name = self.repo_name_edit.text()
        
        if not repo_name:
            QMessageBox.warning(self, "Chyba", "Zadajte názov repozitára")
            return
            
        try:
            # Uloženie konfigurácie
            config_path = self.repo_manager.save_repo_config(repo_type=repo_type, repo_name=repo_name)
            
            if config_path:
                QMessageBox.information(
                    self,
                    "Konfigurácia uložená",
                    f"Konfigurácia repozitára bola uložená do súboru:\n{config_path}"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Chyba",
                    "Nepodarilo sa uložiť konfiguráciu repozitára"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Chyba",
                f"Chyba pri ukladaní konfigurácie: {str(e)}"
            )
            
    def get_repo_info(self):
        """Získa informácie o aktuálne vybranom repozitári"""
        repo_type = self.repo_type_combo.currentData()
        repo_name = self.repo_name_edit.text()
        
        if not repo_name:
            return None
            
        return {
            "type": repo_type,
            "name": repo_name
        }
        
    def setup_copr_auth(self):
        """Zobrazí dialóg pre nastavenie COPR autentifikácie"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Nastavenie COPR autentifikácie")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # Inštrukcie
        instructions = QLabel(
            "Pre používanie COPR repozitárov potrebujete vytvorit konfiguračný súbor "
            "s API tokenmi. Postupujte podľa týchto krokov:"
            "\n\n1. Navštívte https://copr.fedorainfracloud.org/api/"
            "\n2. Prihláste sa (ak ešte nie ste prihlásený)"
            "\n3. Na stránke nájdete vygenerovaný konfiguračný súbor s vašimi API údajmi"
            "\n4. Skopírujte obsah tohto konfiguračného súboru do poľa nižšie"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Odkaz na dokumentáciu
        docs_link = QLabel("<a href='https://docs.pagure.org/copr.copr/user_documentation.html#config-file'>Kliknite sem pre oficiálnu dokumentáciu COPR</a>")
        docs_link.setOpenExternalLinks(True)
        layout.addWidget(docs_link)
        
        # Textové pole pre konfiguráciu
        text_edit = QTextEdit()
        text_edit.setPlaceholderText("[copr-cli]\nlogin = vaše_používateľské_meno\nusername = vaše_používateľské_meno\ntoken = váš_token\ncopr_url = https://copr.fedorainfracloud.org")
        layout.addWidget(text_edit)
        
        # Tlačidlá
        buttons = QHBoxLayout()
        
        cancel_button = QPushButton("Zrušiť")
        cancel_button.clicked.connect(dialog.reject)
        
        save_button = QPushButton("Uložiť konfiguráciu")
        save_button.clicked.connect(lambda: self._save_copr_config(text_edit.toPlainText(), dialog))
        
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        
        layout.addLayout(buttons)
        dialog.setLayout(layout)
        
        dialog.exec_()
        
    def _save_copr_config(self, config_text, dialog):
        """Uloží COPR konfiguráciu do súboru"""
        if not config_text.strip():
            QMessageBox.warning(dialog, "Chyba", "Zadajte konfiguráciu COPR")
            return
            
        try:
            config_path = os.path.expanduser("~/.config/copr")
            
            # Vytvorenie adresára, ak neexistuje
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w') as f:
                f.write(config_text)
                
            QMessageBox.information(
                dialog,
                "Konfigurácia uložená",
                "COPR konfigurácia bola úspešne uložená."
            )
            
            dialog.accept()
            
        except Exception as e:
            QMessageBox.critical(
                dialog,
                "Chyba",
                f"Nepodarilo sa uložiť COPR konfiguráciu: {str(e)}"
            )
            
class AppImageInfoWidget(QWidget):
    """Widget pre zobrazenie a úpravu metadát AppImage"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.metadata = {}
        self.custom_icon_path = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Formulár pre metadáta
        form_layout = QFormLayout()
        
        # Názov aplikácie
        self.name_edit = QLineEdit()
        form_layout.addRow("Názov aplikácie:", self.name_edit)
        
        # Verzia
        self.version_edit = QLineEdit()
        form_layout.addRow("Verzia:", self.version_edit)
        
        # Popis
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        form_layout.addRow("Popis:", self.description_edit)
        
        # Licencia
        self.license_edit = QLineEdit()
        form_layout.addRow("Licencia:", self.license_edit)
        
        # URL
        self.url_edit = QLineEdit()
        form_layout.addRow("Webstránka:", self.url_edit)
        
        # Kategórie
        self.categories_edit = QLineEdit()
        form_layout.addRow("Kategórie:", self.categories_edit)
        
        # Ikona
        icon_layout = QHBoxLayout()
        self.icon_label = QLabel("Žiadna ikona")
        self.icon_label.setMinimumSize(64, 64)
        self.icon_label.setMaximumSize(64, 64)
        self.icon_label.setFrameShape(4)  # Box frame
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        icon_buttons = QVBoxLayout()
        self.select_icon_button = QPushButton("Vybrať ikonu...")
        self.select_icon_button.clicked.connect(self.select_icon)
        
        self.reset_icon_button = QPushButton("Resetovať ikonu")
        self.reset_icon_button.clicked.connect(self.reset_icon)
        self.reset_icon_button.setEnabled(False)
        
        icon_buttons.addWidget(self.select_icon_button)
        icon_buttons.addWidget(self.reset_icon_button)
        
        icon_layout.addWidget(self.icon_label)
        icon_layout.addLayout(icon_buttons)
        icon_layout.addStretch()
        
        form_layout.addRow("Ikona:", icon_layout)
        
        layout.addLayout(form_layout)
        self.setLayout(layout)
        
    def set_metadata(self, metadata):
        self.metadata = metadata
        
        # Nastavenie hodnôt do polí
        self.name_edit.setText(metadata.get('name', ''))
        self.version_edit.setText(metadata.get('version', ''))
        self.description_edit.setText(metadata.get('description', ''))
        self.license_edit.setText(metadata.get('license', ''))
        self.url_edit.setText(metadata.get('homepage', ''))
        
        # Spojenie kategórií do reťazca oddeleného čiarkami
        categories = metadata.get('categories', [])
        if isinstance(categories, list):
            self.categories_edit.setText(';'.join(categories))
        else:
            self.categories_edit.setText(str(categories))
            
        # Zobraziť ikonu, ak existuje
        if 'icon_path' in metadata and metadata['icon_path']:
            self.update_icon_preview(metadata['icon_path'])
            
    def get_metadata(self):
        metadata = self.metadata.copy()
        
        # Aktualizácia hodnôt z polí
        metadata['name'] = self.name_edit.text()
        metadata['version'] = self.version_edit.text()
        metadata['description'] = self.description_edit.toPlainText()
        metadata['license'] = self.license_edit.text()
        metadata['homepage'] = self.url_edit.text()
        
        # Rozdelenie kategórií podľa čiarky/bodkočiarky
        categories_text = self.categories_edit.text()
        if categories_text:
            if ';' in categories_text:
                categories = categories_text.split(';')
            else:
                categories = categories_text.split(',')
            metadata['categories'] = [c.strip() for c in categories if c.strip()]
            
        # Pridanie vlastnej ikony, ak bola vybraná
        if self.custom_icon_path:
            metadata['custom_icon_path'] = self.custom_icon_path
            
        return metadata
        
    def select_icon(self):
        """Výber vlastnej ikony pre aplikáciu"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vybrať ikonu",
            os.path.expanduser("~"),
            "Obrázky (*.png *.jpg *.svg *.xpm);;Všetky súbory (*)"
        )
        
        if file_path:
            self.custom_icon_path = file_path
            self.update_icon_preview(file_path)
            self.reset_icon_button.setEnabled(True)
            
    def reset_icon(self):
        """Resetovanie ikony na pôvodnú z AppImage"""
        self.custom_icon_path = None
        
        # Obnoviť pôvodnú ikonu, ak existuje
        if 'icon_path' in self.metadata and self.metadata['icon_path']:
            self.update_icon_preview(self.metadata['icon_path'])
        else:
            # Vymazať náhľad ikony
            self.icon_label.setPixmap(QPixmap())
            self.icon_label.setText("Žiadna ikona")
            
        self.reset_icon_button.setEnabled(False)
        
    def update_icon_preview(self, icon_path):
        """Aktualizácia náhľadu ikony"""
        if not icon_path or not os.path.exists(icon_path):
            self.icon_label.setText("Ikona neexistuje")
            return
            
        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            self.icon_label.setText("Neplatný formát")
            return
            
        # Upraviť veľkosť pre náhľad
        pixmap = pixmap.scaled(58, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.icon_label.setPixmap(pixmap)
        self.icon_label.setText("")


class MainWindow(QMainWindow):
    """Hlavné okno aplikácie"""
    
    def __init__(self):
        super().__init__()
        self.appimage_path = None
        self.output_dir = None
        self.converter_widget = None
        self.conversion_thread = None
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("AppImage2RPM")
        self.setGeometry(100, 100, 800, 600)
        
        # Centrálny widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Hlavný layout
        main_layout = QVBoxLayout(central_widget)
        
        # Widget pre konverziu
        self.converter_widget = ConverterWidget()
        self.converter_widget.conversion_requested.connect(self.start_conversion)
        main_layout.addWidget(self.converter_widget)
        
    def start_conversion(self, appimage_path, output_dir, metadata):
        """Spustí konverziu AppImage na RPM"""
        self.appimage_path = appimage_path
        self.output_dir = output_dir
        
        # Získanie informácií z widgetov záložiek
        distro_widget = None
        repo_widget = None
        
        # Získanie widgetov zo záložiek
        tab_widget = self.converter_widget.findChild(QTabWidget)
        for i in range(tab_widget.count()):
            widget = tab_widget.widget(i)
            if isinstance(widget, DistroProfileWidget):
                distro_widget = widget
            elif isinstance(widget, RepoManagerWidget):
                repo_widget = widget
                
        # Získanie profilu distribúcie
        distro_profile = None
        if distro_widget:
            distro_profile = distro_widget.get_current_profile()
            
        # Získanie informácií o repozitári
        repo_info = None
        if repo_widget:
            repo_info = repo_widget.get_repo_info()
            
        # Kontrola automatickej detekcie závislostí
        auto_deps = self.converter_widget.check_dependencies.isChecked()
        
        # Vytvorenie a spustenie vlákna pre konverziu
        self.conversion_thread = ConversionThread(
            self.appimage_path,
            self.output_dir,
            metadata,
            distro_profile,
            auto_deps=auto_deps,
            repo_info=repo_info
        )
        
        self.conversion_thread.progress_signal.connect(self.converter_widget.update_progress)
        self.conversion_thread.finished_signal.connect(self.conversion_finished)
        
        self.conversion_thread.start()
        self.converter_widget.disable_controls(True)
        
    def conversion_finished(self, success, rpm_path, message):
        """Callback po dokončení konverzie"""
        self.converter_widget.disable_controls(False)
        
        if success:
            # Úspešná konverzia
            QMessageBox.information(
                self,
                "Konverzia dokončená",
                f"RPM balík bol úspešne vytvorený v:\n{rpm_path}\n\n{message}"
            )
            
            # Otvorenie priečinka s výsledným RPM
            if rpm_path:
                self.open_output_directory(os.path.dirname(rpm_path))
        else:
            # Neúspešná konverzia
            QMessageBox.critical(
                self,
                "Chyba pri konverzii",
                f"Nepodarilo sa vytvoriť RPM balík.\n\n{message}"
            )
            
    def open_output_directory(self, directory):
        """Otvorí priečinok v správcovi súborov"""
        try:
            if sys.platform == 'win32':
                os.startfile(directory)
            elif sys.platform == 'darwin':
                subprocess.call(['open', directory])
            else:
                subprocess.call(['xdg-open', directory])
        except Exception as e:
            logger.error(f"Chyba pri otváraní priečinka: {e}")


class ConverterWidget(QWidget):
    """Widget pre konverziu AppImage na RPM"""
    
    conversion_requested = pyqtSignal(str, str, dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.appimage_path = None
        self.output_dir = os.path.expanduser("~/rpmbuild/RPMS")
        self.appimage_info = None
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        # Výber súboru
        file_group = QGroupBox("Výber súboru")
        file_layout = QVBoxLayout()
        
        file_input_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Cesta k AppImage súboru")
        self.file_input.setReadOnly(True)
        
        self.browse_button = QPushButton("Prehľadávať")
        self.browse_button.clicked.connect(self.browse_appimage)
        
        file_input_layout.addWidget(self.file_input)
        file_input_layout.addWidget(self.browse_button)
        
        file_layout.addLayout(file_input_layout)
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # Výstupný adresár
        output_group = QGroupBox("Výstupný adresár")
        output_layout = QVBoxLayout()
        
        output_input_layout = QHBoxLayout()
        self.output_input = QLineEdit(self.output_dir)
        self.output_input.setPlaceholderText("Cesta k výstupnému adresáru")
        
        self.output_button = QPushButton("Prehľadávať")
        self.output_button.clicked.connect(self.browse_output_dir)
        
        output_input_layout.addWidget(self.output_input)
        output_input_layout.addWidget(self.output_button)
        
        output_layout.addLayout(output_input_layout)
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)
        
        # Záložky s nastaveniami
        tab_widget = QTabWidget()
        
        # Základné nastavenia
        basic_widget = QWidget()
        basic_layout = QVBoxLayout()
        
        # AppImage info widget
        self.appimage_info_widget = AppImageInfoWidget()
        basic_layout.addWidget(self.appimage_info_widget)
        
        basic_widget.setLayout(basic_layout)
        tab_widget.addTab(basic_widget, "Základné nastavenia")
        
        # Pokročilé nastavenia
        advanced_widget = QWidget()
        advanced_layout = QVBoxLayout()
        
        # Checkbox pre automatickú detekciu závislostí
        self.check_dependencies = QCheckBox("Automaticky detekovať závislosti")
        self.check_dependencies.setChecked(True)
        advanced_layout.addWidget(self.check_dependencies)
        
        # Nastavenia závislostí
        dependencies_group = QGroupBox("Závislosti")
        dependencies_layout = QVBoxLayout()
        
        self.dependencies_list = QListWidget()
        dependencies_layout.addWidget(self.dependencies_list)
        
        dependencies_buttons = QHBoxLayout()
        self.add_dependency_button = QPushButton("Pridať závislosť")
        self.add_dependency_button.clicked.connect(self.add_dependency)
        
        self.remove_dependency_button = QPushButton("Odstrániť")
        self.remove_dependency_button.clicked.connect(self.remove_dependency)
        
        dependencies_buttons.addWidget(self.add_dependency_button)
        dependencies_buttons.addWidget(self.remove_dependency_button)
        dependencies_buttons.addStretch()
        
        dependencies_layout.addLayout(dependencies_buttons)
        dependencies_group.setLayout(dependencies_layout)
        advanced_layout.addWidget(dependencies_group)
        
        advanced_widget.setLayout(advanced_layout)
        tab_widget.addTab(advanced_widget, "Pokročilé nastavenia")
        
        # Widget pre správu repozitárov
        repo_widget = RepoManagerWidget()
        tab_widget.addTab(repo_widget, "Repozitár")
        
        # Widget pre správu profilov distribúcií
        distro_widget = DistroProfileWidget()
        tab_widget.addTab(distro_widget, "Distribúcia")
        
        main_layout.addWidget(tab_widget)
        
        # Progress bar
        progress_group = QGroupBox("Priebeh konverzie")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        self.status_label = QLabel("Pripravený na konverziu")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # Tlačidlá
        buttons_layout = QHBoxLayout()
        
        self.convert_button = QPushButton("Konvertovať")
        self.convert_button.clicked.connect(self.request_conversion)
        self.convert_button.setEnabled(False)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.convert_button)
        
        main_layout.addLayout(buttons_layout)
        
        self.setLayout(main_layout)
        
    def browse_appimage(self):
        """Otvorí dialóg pre výber AppImage súboru"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte AppImage súbor",
            os.path.expanduser("~"),
            "AppImage súbory (*.AppImage);;Všetky súbory (*)"
        )
        
        if file_path:
            self.appimage_path = file_path
            self.file_input.setText(file_path)
            self.convert_button.setEnabled(True)
            
            # Načítanie metadát z AppImage
            try:
                extractor = AppImageExtractor(file_path)
                metadata = extractor.parse_metadata()
                
                # Nastavenie metadát do AppImageInfoWidget
                self.appimage_info_widget.set_metadata(metadata)
                
                # Vyčistenie extrahovaných súborov
                extractor.cleanup()
                
            except Exception as e:
                logger.error(f"Chyba pri načítaní metadát: {e}", exc_info=True)
                QMessageBox.warning(
                    self,
                    "Chyba pri načítaní metadát",
                    f"Nepodarilo sa načítať metadáta z AppImage súboru: {str(e)}"
                )
                
    def browse_output_dir(self):
        """Otvorí dialóg pre výber výstupného adresára"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Vyberte výstupný adresár",
            self.output_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.output_dir = directory
            self.output_input.setText(directory)
            
    def add_dependency(self):
        """Pridá závislosť do zoznamu"""
        # Jednoduchý dialóg pre zadanie závislosti
        dependency, ok = QInputDialog.getText(
            self,
            "Pridať závislosť",
            "Zadajte názov balíka (napr. 'glibc >= 2.28'):"
        )
        
        if ok and dependency:
            self.dependencies_list.addItem(dependency)
            
    def remove_dependency(self):
        """Odstráni vybranú závislosť zo zoznamu"""
        selected_items = self.dependencies_list.selectedItems()
        
        for item in selected_items:
            self.dependencies_list.takeItem(self.dependencies_list.row(item))
            
    def request_conversion(self):
        """Spustí konverziu AppImage na RPM"""
        if not self.appimage_path:
            QMessageBox.warning(
                self,
                "Chyba",
                "Vyberte AppImage súbor pre konverziu"
            )
            return
            
        # Aktualizácia výstupného adresára z textu
        self.output_dir = self.output_input.text()
        
        # Kontrola, či výstupný adresár existuje
        if not os.path.isdir(self.output_dir):
            try:
                os.makedirs(self.output_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Chyba",
                    f"Nepodarilo sa vytvoriť výstupný adresár: {str(e)}"
                )
                return
                
        # Získanie metadát z AppImageInfoWidget
        metadata = self.appimage_info_widget.get_metadata()
        
        # Pridanie závislostí z pokročilých nastavení
        if not self.check_dependencies.isChecked():
            dependencies = []
            for i in range(self.dependencies_list.count()):
                dependencies.append(self.dependencies_list.item(i).text())
                
            if dependencies:
                metadata["requires"] = dependencies
                
        # Emit signál pre konverziu
        self.conversion_requested.emit(self.appimage_path, self.output_dir, metadata)
        
    def update_progress(self, value, message):
        """Aktualizuje progress bar a správu o stave"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        
    def disable_controls(self, disabled):
        """Zapne/vypne ovládacie prvky počas konverzie"""
        self.browse_button.setEnabled(not disabled)
        self.output_button.setEnabled(not disabled)
        self.convert_button.setEnabled(not disabled)


def main():
    """Hlavná funkcia aplikácie"""
    # Kontrola závislostí
    try:
        # Kontrola RPM nástrojov
        process = subprocess.run(
            ["which", "rpmbuild"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if process.returncode != 0:
            print("CHYBA: rpmbuild nie je nainštalovaný. Nainštalujte balík 'rpm-build':")
            print("  sudo dnf install rpm-build rpmdevtools")
            return 1
            
    except Exception as e:
        print(f"CHYBA pri kontrole závislostí: {e}")
        return 1
        
    # Spustenie aplikácie
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Konzistentný štýl na všetkých platformách
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
