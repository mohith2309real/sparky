"""Translation-ready core UI, with local Hindi and Telugu beta catalogs."""
from PyQt6.QtCore import QObject,QEvent
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import (QAbstractButton,QApplication,QComboBox,QLabel,QLineEdit,QListWidget,QWidget)
CATALOG={
'Run':('चलाएँ','నడుపు'),'Stop':('रोकें','ఆపు'),'Step':('एक कदम','ఒక్క అడుగు'),'Upload':('अपलोड','అప్‌లోడ్'),
'&File':('&फ़ाइल','&ఫైల్'),'&Edit':('&संपादन','&సవరించు'),'&View':('&दृश्य','&వీక్షణ'),
'&Run':('&चलाएँ','&నడుపు'),'&Learn':('&सीखें','&నేర్చుకో'),'&Help':('&मदद','&సహాయం'),
'Home':('होम','హోమ్'),'Settings':('सेटिंग्स','సెట్టింగులు'),'General':('सामान्य','సాధారణ'),
'Editor':('संपादक','ఎడిటర్'),'Stage & sounds':('मंच और आवाज़','వేదిక మరియు శబ్దాలు'),
'Languages':('भाषाएँ','భాషలు'),'Updates':('अपडेट','అప్‌డేట్లు'),'Accessibility':('सुलभता','సౌలభ్యం'),
'Privacy':('गोपनीयता','గోప్యత'),'About':('परिचय','గురించి'),'Classroom':('कक्षा','తరగతి'),
'New program':('नया प्रोग्राम','కొత్త ప్రోగ్రామ్'),'Open a file':('फ़ाइल खोलें','ఫైల్ తెరువు'),
'Learn to code':('कोड लिखना सीखें','కోడ్ నేర్చుకో'),'Take the tour':('ऐप की सैर करें','యాప్ పర్యటన'),
'New project…':('नया प्रोजेक्ट…','కొత్త ప్రాజెక్ట్…'),'Open…':('खोलें…','తెరువు…'),
'Save':('सहेजें','దాచు'),'Save as…':('ऐसे सहेजें…','ఇలా దాచు…'),'Close':('बंद करें','మూసివేయి'),
'Cancel':('रद्द करें','రద్దు'),'Next':('अगला','తరువాత'),'Back':('पीछे','వెనుకకు'),'Skip':('छोड़ें','దాటవేయి'),
'Blocks':('ब्लॉक','బ్లాకులు'),'Files':('फ़ाइलें','ఫైళ్లు'),'Outline':('रूपरेखा','రూపురేఖలు'),
'Debug':('त्रुटि खोजें','దోషాలు వెతుకు'),'Extensions':('एक्सटेंशन','విస్తరణలు'),'AI helper':('AI सहायक','AI సహాయకుడు'),
'Good morning!':('सुप्रभात!','శుభోదయం!'),'Good afternoon!':('नमस्कार!','శుభ మధ్యాహ్నం!'),
'Good evening!':('शुभ संध्या!','శుభ సాయంత్రం!'),'What do you want to make today?':('आज आप क्या बनाना चाहते हैं?','ఈ రోజు ఏమి తయారు చేయాలనుకుంటున్నారు?'),
'New program…':('नया प्रोग्राम…','కొత్త ప్రోగ్రామ్…'),'Ready':('तैयार','సిద్ధం'),
'Lessons and challenges':('पाठ और चुनौतियाँ','పాఠాలు మరియు సవాళ్లు'),
'Explain this line':('इस पंक्ति को समझाएँ','ఈ పంక్తిని వివరించు'),'Examples':('उदाहरण','ఉదాహరణలు'),
'Help':('मदद','సహాయం'),'Check my work':('मेरा काम जाँचें','నా పని తనిఖీ చేయి'),
'Try this code':('यह कोड आज़माएँ','ఈ కోడ్ ప్రయత్నించు'),'Try the challenge':('चुनौती आज़माएँ','సవాలు ప్రయత్నించు'),
'Hint':('संकेत','సూచన'),'Reference':('संदर्भ','సూచన గ్రంథం'),'Glossary':('शब्दावली','పదకోశం'),
'Achievements':('उपलब्धियाँ','విజయాలు'),'Daily challenge':('आज की चुनौती','రోజువారీ సవాలు'),
'Progress report':('प्रगति रिपोर्ट','ప్రగతి నివేదిక'),'World certificate':('दुनिया का प्रमाणपत्र','ప్రపంచ ధ్రువపత్రం'),
'Preview theme':('थीम देखें','థీమ్ ముందుగా చూడు'),'Export settings':('सेटिंग्स निर्यात करें','సెట్టింగులు ఎగుమతి చేయి'),
'Import settings':('सेटिंग्स आयात करें','సెట్టింగులు దిగుమతి చేయి'),'Send':('भेजें','పంపు'),
'Clear chat':('चैट साफ़ करें','చాట్ తొలగించు'),'What gets sent':('क्या भेजा जाता है','ఏమి పంపబడుతుంది'),
'Preview':('पहले देखें','ముందుగా చూడు'),'Sound library':('आवाज़ों का संग्रह','శబ్దాల గ్రంథాలయం'),
'Create project':('प्रोजेक्ट बनाएँ','ప్రాజెక్ట్ సృష్టించు'),'Name':('नाम','పేరు')}


def translate(text,language='en'):
    for english,variants in CATALOG.items():
        if text==english or text in variants:
            return english if language=='en' else variants[0 if language=='hi' else 1]
    return text


class Translator(QObject):
    def __init__(self,app):
        super().__init__(app); self.language='en'; app.installEventFilter(self)

    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Show and isinstance(obj,QWidget): self.apply(obj)
        return False

    def apply(self,root):
        for obj in [root,*root.findChildren(QWidget),*root.findChildren(QAction)]:
            if isinstance(obj,(QAbstractButton,QLabel,QAction)):
                obj.setText(translate(obj.text(),self.language))
                if isinstance(obj,QWidget) and (not obj.accessibleName() or obj.property('sparky_generated_name')):
                    document=QTextDocument(); document.setHtml(obj.text())
                    obj.setAccessibleName(document.toPlainText().replace('&',''))
                    obj.setProperty('sparky_generated_name',True)
                if isinstance(obj,QLabel) and obj.buddy() and not obj.buddy().accessibleName():
                    obj.buddy().setAccessibleName(obj.text().replace('&',''))
            if isinstance(obj,QLineEdit):
                obj.setPlaceholderText(translate(obj.placeholderText(),self.language))
                if not obj.accessibleName(): obj.setAccessibleName(obj.placeholderText() or 'Text field')
            if isinstance(obj,QListWidget):
                for i in range(obj.count()): obj.item(i).setText(translate(obj.item(i).text(),self.language))
            if isinstance(obj,QWidget) and not obj.accessibleName() and obj.toolTip():
                obj.setAccessibleName(obj.toolTip())

    def set_language(self,language):
        self.language=language if language in ('en','hi','te') else 'en'
        for widget in QApplication.topLevelWidgets(): self.apply(widget)


def translator():
    app=QApplication.instance()
    if not hasattr(app,'sparky_translator'): app.sparky_translator=Translator(app)
    return app.sparky_translator
